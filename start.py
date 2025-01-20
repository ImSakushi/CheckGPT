import os
import re
import requests
import discord
from openai import OpenAI
from bs4 import BeautifulSoup
from discord import app_commands
from textwrap import wrap

DEEPSEEK_API_KEY = "sk-token"
DISCORD_TOKEN = "discord-token"

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

ALLOWED_ROLE_ID = 780835397008621600

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

async def analyze_content(content, doc_name):
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        
        system_prompt = """Tu es un correcteur de manga professionnel. Respecte strictement :
        1. Liste TOUTES les fautes (orthographe, grammaire, virgules)
        2. Formate exactement comme :
        **Page XX - Bulle XX**
        - [phrase avec **erreur en gras**] -> [correction]
        => [explication courte]
        3. N'invente rien
        4. Ignore les abréviations du langage familier ("j'pense", "Nan") 
        5. Ne signale pas les négations manquantes comme "ne" dans "je sais pas", c'est du langage familier normal
        6. IMPORTANT : **Ne signale pas les majuscules manquantes ou mauvais apostrophes**
        """
        
        response = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"DOCUMENT À CORRIGER :\n{content}"}
            ]
        )
        
        return format_corrections(response.choices[0].message.content, doc_name)

    except Exception as e:
        print(f"Erreur DeepSeek: {e}")
        return None

async def process_check(interaction: discord.Interaction, lien: str):
    try:
        doc_name = get_gdoc_title(lien)
        gdoc_id = re.search(r'/d/([a-zA-Z0-9-_]+)', lien).group(1)
        export_url = f"https://docs.google.com/document/d/{gdoc_id}/export?format=txt"
        
        response = requests.get(export_url)
        response.raise_for_status()
        content = response.text
        
        corrections = await analyze_content(content, doc_name)
        
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
@app_commands.check(has_allowed_role)
async def slash_check(interaction: discord.Interaction, lien: str):
    await interaction.response.defer()
    await process_check(interaction, lien)

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