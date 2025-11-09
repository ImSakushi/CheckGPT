# CheckGPT

Ce bot Discord relit automatiquement les chapitres de manga stockés dans Google Docs en utilisant l'API Responses
de GPT-5. Il liste les fautes d'orthographe et de grammaire en respectant un format précis pour que
les correcteurs puissent appliquer les modifications facilement.

## Fonctionnalités

- Récupère un document Google Docs via son lien
- Envoie tout le texte à GPT-5 avec un prompt expert
- Renvoie les corrections formatées dans Discord (gestion de chunk si >2000 caractères)
- Autorise uniquement les membres avec le rôle configuré `ALLOWED_ROLE_ID`

## Installation

1. **Cloner le dépôt** et ouvrir le dossier :
   ```bash
   git clone https://github.com/ImSakushi/CheckGPT
   cd CheckGPT
   ```
2. **Créer un environnement virtuel** et activer (mais vous pouvez faire sans):
   ```bash
   python -m venv venv
   # Sous Windows
   venv\Scripts\activate
   # Sous macOS / Linux
   source venv/bin/activate
   ```
3. **Installer les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Copie le fichier `.env` (fourni) et complète les valeurs :

```
DISCORD_TOKEN=...
OPENAI_API_KEY=...
ALLOWED_ROLE_ID=...
# OPENAI_MODEL=gpt-5  # facultatif, garde la valeur par défaut si non défini
```

- `DISCORD_TOKEN` : jeton du bot Discord
 - `OPENAI_API_KEY` : clé pour l'API OpenAI Responses
- `ALLOWED_ROLE_ID` : ID du rôle autorisé à lancer `/check`
- `OPENAI_MODEL` : (optionnel) modèle à utiliser — `gpt-5-thinking-high` par défaut

## Lancer le bot

```bash
python main.py
```

Le bot se connecte, synchronise les commandes slash et écoute les context menus `check`.
