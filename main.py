import os
import asyncio
import re
import requests
import discord
import openai
from openai import OpenAI
from bs4 import BeautifulSoup
from discord import app_commands
from textwrap import wrap
from dotenv import load_dotenv
from prompt_config import PROMPT_CORRECTEUR

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN manquant dans l'environnement ou le fichier .env.")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY manquant dans l'environnement ou le fichier .env.")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

ALLOWED_ROLE_ID = os.getenv("ALLOWED_ROLE_ID")
if not ALLOWED_ROLE_ID:
    raise RuntimeError("ALLOWED_ROLE_ID manquant dans l'environnement ou le fichier .env.")

try:
    ALLOWED_ROLE_ID = int(ALLOWED_ROLE_ID)
except ValueError:
    raise RuntimeError("ALLOWED_ROLE_ID doit être un entier valide.")

try:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
except Exception:
    openai_client = openai
    openai_client.api_key = OPENAI_API_KEY


def get_responses_handler():
    handler = getattr(openai_client, "responses", None)
    if handler:
        return handler
    handler = getattr(openai, "responses", None)
    if handler:
        return handler
    raise RuntimeError(
        "Impossible d'accéder à l'API Responses. Mettez à jour openai>=1.12.0 ou "
        "utilisez un client compatible."
    )

def get_gdoc_title(gdoc_link):
    try:
        response = requests.get(gdoc_link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find('title')
        
        if title_tag:
            raw_title = title_tag.get_text()
            clean_title = re.sub(r'\s*-\s*Google\s+Docs$', '', raw_title, flags=re.IGNORECASE)
            return clean_title.strip() or "Document sans titre"
        return "Document sans titre"
        
    except Exception as e:
        print(f"Erreur récupération titre : {e}")
        return "Document Google"

async def has_allowed_role(interaction: discord.Interaction) -> bool:
    return any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles)

def format_corrections(content, doc_name):
    return f"# 📝 Corrections pour '{doc_name}'\n\n{content}"

def extract_response_text(response):
    # Primary shortcut when API exposes a flattened output text field.
    fallback_text = getattr(response, "output_text", None)
    if fallback_text:
        return fallback_text.strip()

    texts = []
    for item in getattr(response, "output", []):
        for piece in getattr(item, "content", []):
            # handle both explicit output_text pieces and generic text fields
            piece_type = getattr(piece, "type", None)
            if piece_type == "output_text" and getattr(piece, "text", None):
                texts.append(piece.text)
            elif getattr(piece, "text", None):
                texts.append(piece.text)
    if texts:
        return "".join(texts).strip()

    # handle legacy attribute names
    legacy = getattr(response, "output", None)
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()
    return ""

async def analyze_content(content, doc_name, reasoning_effort="high"):
    try:
        responses_handler = get_responses_handler()
        response = await asyncio.to_thread(
            responses_handler.create,
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": PROMPT_CORRECTEUR,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"Voici ton script :\n\n{content}",
                        }
                    ],
                },
            ],
            text={
                "format": {
                    "type": "text",
                },
                "verbosity": "medium",
            },
            reasoning={
                "effort": reasoning_effort,
                "summary": "auto",
            },
            tools=[],
            store=True,
            include=[
                "reasoning.encrypted_content",
                "web_search_call.action.sources",
            ],
        )

        corrections = extract_response_text(response)
        if not corrections:
            return None

        return format_corrections(corrections, doc_name)

    except Exception as e:
        print(f"Erreur OpenAI: {e}")
        return None

async def process_check(interaction: discord.Interaction, lien: str, reasoning_effort="high"):
    try:
        doc_name = get_gdoc_title(lien)
        gdoc_id = re.search(r'/d/([a-zA-Z0-9-_]+)', lien).group(1)
        export_url = f"https://docs.google.com/document/d/{gdoc_id}/export?format=txt"
        
        response = requests.get(export_url)
        response.raise_for_status()
        content = response.text
        
        corrections = await analyze_content(content, doc_name, reasoning_effort=reasoning_effort)
        
        if not corrections:
            return await interaction.followup.send("✅ Aucune erreur détectée !")
        
        channel = interaction.channel
        chunks = wrap(corrections, 2000, replace_whitespace=False)
        
        await interaction.followup.send(chunks[0])
        
        for chunk in chunks[1:]:
            await channel.send(chunk)

    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {str(e)}")

class CheckContextMenu(app_commands.ContextMenu):
    def __init__(self):
        super().__init__(
            name="check",
            callback=self.check_message,
            type=discord.AppCommandType.message
        )

    async def check_message(self, interaction: discord.Interaction, message: discord.Message):
        if not await has_allowed_role(interaction):
            await interaction.response.send_message(
                "🔒 Accès réservé aux correcteurs certifiés !", 
                ephemeral=True
            )
            return

        await interaction.response.defer()
        gdoc_links = re.findall(r'https?://docs\.google\.com/document/d/[\w-]+', message.content)
        
        if not gdoc_links:
            return await interaction.followup.send("❌ Aucun lien Google Docs valide trouvé", ephemeral=True)
        
        await process_check(interaction, gdoc_links[0])

@tree.command(name="check", description="Corrige un script de manga depuis Google Docs")
@app_commands.choices(
    effort=[
        app_commands.Choice(name="Minimal", value="minimal"),
        app_commands.Choice(name="Low", value="low"),
        app_commands.Choice(name="Medium", value="medium"),
        app_commands.Choice(name="High", value="high"),
    ]
)
@app_commands.check(has_allowed_role)
async def slash_check(
    interaction: discord.Interaction,
    lien: str,
    effort: str = "high",
):
    await interaction.response.defer()
    await process_check(interaction, lien, reasoning_effort=effort)

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "🔒 Accès réservé aux correcteurs certifiés !",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"⚠️ Erreur : {str(error)}",
            ephemeral=True
        )

check_context = CheckContextMenu()
tree.add_command(check_context)

@client.event
async def on_ready():
    await tree.sync()
    print(f"Connecté en tant que {client.user}")

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
