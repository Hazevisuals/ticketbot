import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Modal, TextInput
import os
import json
from datetime import datetime, timedelta
import pytz
import threading
from flask import Flask, request
import aiohttp
import asyncio
import subprocess
import hashlib
import random

# Flask app for health checks (required for Autoscale deployment)
app = Flask(__name__)

@app.route('/')
def health_check():
    return {'status': 'healthy', 'service': 'discord-bot'}, 200

@app.route('/health')
def health():
    return {'status': 'ok'}, 200

# GitHub Webhook für automatische Updates
@app.route('/webhook', methods=['POST'])
def github_webhook():
    """GitHub Webhook Handler für automatische Updates"""
    try:
        # Verify GitHub webhook (optional - add secret validation here)
        payload = request.get_json()
        
        if payload and 'head_commit' in payload:
            print(f"🔄 GitHub Update erhalten: {payload['head_commit']['message']}")
            
            # Trigger bot update in background
            threading.Thread(target=trigger_bot_update, daemon=True).start()
            
            return {'status': 'update_triggered'}, 200
        
        return {'status': 'no_update_needed'}, 200
        
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return {'status': 'error'}, 500

def trigger_bot_update():
    """Trigger Bot Update Process"""
    try:
        print("🚀 Starte automatisches Bot-Update...")
        
        # Git pull (if in git environment)
        try:
            subprocess.run(['git', 'pull'], check=True, capture_output=True)
            print("✅ Code erfolgreich aktualisiert")
        except:
            print("⚠️ Git pull fehlgeschlagen - möglicherweise keine Git-Umgebung")
        
        # Schedule Discord updates
        if bot and hasattr(bot, 'loop'):
            asyncio.run_coroutine_threadsafe(
                schedule_discord_updates(), 
                bot.loop
            )
        
    except Exception as e:
        print(f"❌ Update Error: {e}")

async def schedule_discord_updates():
    """Schedule Discord component updates"""
    try:
        print("🔄 Starte Discord-Updates...")
        
        # Update all server panels
        await update_all_ticket_panels()
        
        # Notify admins about update
        await notify_admins_about_update()
        
        print("✅ Discord-Updates abgeschlossen")
        
    except Exception as e:
        print(f"❌ Discord Update Error: {e}")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Preis-Datenbank - Standard-Preise
default_preise = {
    "Clothing": "👕 Weste: 20€\n👖 Hose: 10€\n👕 Top: 10€\n😷 Maske: 10€\n➡️ Jegliche Kleidung: auf Anfrage",
    "Clothing Packages": "📦 Kleidungspaket: 20€\n🦺 Bikerweste: 20€\n(Hinweis: Alle anderen Pakete je 10€)",
    "Biker Packages": "🏍️ Custom Biker-Kleidung auf Anfrage.",
    "Chains": "⛓️ Custom Chains: 10–20€ je nach Modell.",
    "Weaponskins": "🔫 Custom Waffenskins: Preis auf Anfrage."
}

# Lade Preise aus Datei oder verwende Standard-Preise
def load_prices():
    try:
        with open('prices.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default_preise.copy()

# Speichere Preise in Datei
def save_prices(prices):
    with open('prices.json', 'w', encoding='utf-8') as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)

preise = load_prices()

# Berechtigung-Check (nur Server-Admins oder bestimmte Rollen können Preise bearbeiten)
def is_authorized(user, guild):
    print(f"🔍 Berechtigungs-Check für {user} in Guild: {guild}")
    
    if guild is None:
        print("❌ Guild ist None")
        return False
    
    member = guild.get_member(user.id)
    print(f"🔍 Member gefunden: {member}")
    
    if member is None:
        print("❌ Member ist None")
        return False
    
    # Prüfe ob der User Administrator-Rechte hat
    admin_perms = member.guild_permissions.administrator
    print(f"🔍 Administrator-Berechtigung: {admin_perms}")
    
    if admin_perms:
        print("✅ User ist Administrator - Zugriff gewährt")
        return True
    
    # Prüfe ob der User eine der erlaubten Rollen hat
    authorized_roles = ["Admin", "Moderator", "Haze Visuals Team", "Management", "HV | Leitung"]  # Anpassbar
    user_roles = [role.name for role in member.roles]
    print(f"🔍 User Rollen: {user_roles}")
    print(f"🔍 Erlaubte Rollen: {authorized_roles}")
    
    for role in member.roles:
        if role.name in authorized_roles:
            print(f"✅ User hat erlaubte Rolle '{role.name}' - Zugriff gewährt")
            return True
    
    print("❌ User hat keine Berechtigung")
    return False

# Event: Bot startet
@bot.event
async def on_ready():
    print(f"✅ Eingeloggt als {bot.user}")
    print(f"📊 Bot ist in {len(bot.guilds)} Server(n)")
    
    # Liste alle Server auf
    for guild in bot.guilds:
        print(f"   📋 Server: {guild.name} (ID: {guild.id}) - {guild.member_count} Mitglieder")
        
        # Überprüfe Bot-Berechtigungen in diesem Server
        bot_member = guild.get_member(bot.user.id)
        if bot_member:
            perms = bot_member.guild_permissions
            print(f"      🔑 Berechtigungen: use_application_commands={perms.use_application_commands}, send_messages={perms.send_messages}")
        
        # Versuche guild-spezifische Synchronisation (aggressiver)
        try:
            # Clear guild commands first to prevent conflicts
            bot.tree.clear_commands(guild=guild)
            synced_guild = await bot.tree.sync(guild=guild)
            print(f"      ✅ {len(synced_guild)} Commands für Server {guild.name} synchronisiert")
        except Exception as e:
            print(f"      ❌ Fehler beim Server-Sync für {guild.name}: {e}")
    
    # Globale Synchronisation (aggressiver)
    try:
        # Force a clean sync
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} Globale Slash Commands synchronisiert")
        for cmd in synced:
            print(f"   - /{cmd.name}: {cmd.description}")
    except Exception as e:
        print(f"❌ Fehler beim globalen Synchronisieren: {e}")
        # Try backup sync
        try:
            bot.tree.clear_commands(guild=None)
            synced = await bot.tree.sync()
            print(f"✅ Backup-Sync erfolgreich: {len(synced)} Commands")
        except Exception as backup_error:
            print(f"❌ Backup-Sync fehlgeschlagen: {backup_error}")
    
    # Start the background task after bot is ready
    if not check_tickets_task.is_running():
        check_tickets_task.start()
        print("🔄 Ticket-Überwachung gestartet")
    
    # Start the calendar and cleanup tasks
    if not weekly_calendar_update.is_running():
        weekly_calendar_update.start()
        print("📅 Kalender-System gestartet")
    
    # Ensure ticket counter channel exists for each guild
    for guild in bot.guilds:
        await ensure_ticket_counter_channel_exists(guild)
        await ensure_member_counter_channel_exists(guild)

@bot.event
async def on_message(message):
    """Handle messages - check for admin image uploads to set as banners"""
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Check if user is admin/server owner and posted an image
    if message.guild and (message.author.guild_permissions.administrator or message.author == message.guild.owner):
        # Check if message has image attachments
        if message.attachments:
            for attachment in message.attachments:
                # Check if attachment is an image
                if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                    try:
                        # Set new banner URL to the image URL
                        set_server_banner_url(message.guild.id, attachment.url)
                        
                        # Send confirmation
                        embed = discord.Embed(
                            title="🖼️ Banner aktualisiert!",
                            description=f"Das neue Banner wurde erfolgreich gesetzt.\n\n"
                                      f"**Hochgeladen von:** {message.author.mention}\n"
                                      f"**Dateiname:** {attachment.filename}\n"
                                      f"**Größe:** {attachment.size:,} Bytes\n\n"
                                      f"Das neue Banner wird ab sofort in allen Bot-Nachrichten verwendet!",
                            color=0x00ff00
                        )
                        embed.set_image(url=attachment.url)
                        embed.set_footer(text="Haze Visuals • Banner System")
                        
                        await message.reply(embed=embed)
                        print(f"🖼️ Banner updated for guild {message.guild.name} by {message.author}: {attachment.url}")
                        return  # Only process first image
                        
                    except Exception as e:
                        print(f"❌ Error setting banner: {e}")
                        await message.reply("❌ Fehler beim Setzen des Banners. Bitte versuche es erneut.")
    
    # Process commands
    await bot.process_commands(message)
    
    # Clear any cached interactions to prevent "interaction failed" errors
    print("🔄 Bot bereit - Interaktionen wurden aktualisiert")
    
    # Start auto-update checking
    check_for_updates.start()
    print(f"🚀 Auto-Update System gestartet (Version {BOT_VERSION})")

# Add error handler for interaction failures
@bot.event
async def on_error(event, *args, **kwargs):
    """Handle errors gracefully"""
    import traceback
    print(f"❌ Bot Error in {event}: {traceback.format_exc()}")

# Handle interaction errors specifically
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Handle application command errors"""
    print(f"❌ Command Error: {error}")
    if not interaction.response.is_done():
        try:
            await interaction.response.send_message("❌ Ein Fehler ist aufgetreten. Bitte versuche es erneut.", ephemeral=True)
        except:
            pass

# Welcome message when user joins
@bot.event
async def on_member_join(member):
    """Send welcome message when user joins"""
    try:
        config = get_server_config(member.guild.id)
        
        # Check if welcome messages are enabled
        if not config["features"]["welcome_messages"]:
            return
        
        welcome_channel_id = config["channels"]["welcome_channel"]
        if welcome_channel_id:
            welcome_channel = bot.get_channel(welcome_channel_id)
            if welcome_channel:
                welcome_msg = f"Willkommen {member.mention} auf Haze Visuals. Viel Spaß !"
                await welcome_channel.send(welcome_msg)
                print(f"👋 Welcome message sent for {member}")
        
        # Update member counter
        await update_member_counter_channel(member.guild)
        
    except Exception as e:
        print(f"❌ Error sending welcome message: {e}")

# Leave message when user leaves
@bot.event
async def on_member_remove(member):
    """Send leave message when user leaves"""
    try:
        config = get_server_config(member.guild.id)
        
        # Check if leave messages are enabled
        if not config["features"]["leave_messages"]:
            return
        
        leave_channel_id = config["channels"]["leave_channel"]
        if leave_channel_id:
            leave_channel = bot.get_channel(leave_channel_id)
            if leave_channel:
                leave_msg = f"{member.name} hat uns verlassen"
                await leave_channel.send(leave_msg)
                print(f"👋 Leave message sent for {member}")
        
        # Update member counter
        await update_member_counter_channel(member.guild)
        
    except Exception as e:
        print(f"❌ Error sending leave message: {e}")

# Test command with prefix (for debugging)
@bot.command(name="test")
async def test_cmd(ctx):
    print(f"📌 Test command verwendet von {ctx.author} in {ctx.guild.name if ctx.guild else 'DM'}")
    await ctx.send("✅ Bot funktioniert! Versuche `/preise` zu verwenden.")

# Debug command to check bot status
@bot.command(name="debug")
async def debug_cmd(ctx):
    print(f"📌 Debug command verwendet von {ctx.author}")
    embed = discord.Embed(title="🔍 Bot Debug Info", color=0x00ff00)
    embed.add_field(name="Bot User", value=f"{bot.user.name}", inline=False)
    embed.add_field(name="Server", value=ctx.guild.name if ctx.guild else "DM", inline=False)
    embed.add_field(name="Slash Commands", value="Verwende `/preise` um die Preisliste zu sehen", inline=False)
    
    if ctx.guild:
        bot_member = ctx.guild.get_member(bot.user.id)
        perms = bot_member.guild_permissions
        embed.add_field(name="Berechtigungen", 
                       value=f"Send Messages: {perms.send_messages}\nUse Application Commands: {perms.use_application_commands}", 
                       inline=False)
    
    await ctx.send(embed=embed)

# Modal für Preis-Bearbeitung
class PriceEditModal(Modal):
    def __init__(self, category_name: str, current_price: str):
        super().__init__(title=f"Preise bearbeiten: {category_name}")
        self.category_name = category_name
        
        self.price_input = TextInput(
            label="Neue Preise",
            placeholder="Gib die neuen Preise ein...",
            default=current_price,
            style=discord.TextStyle.long,
            max_length=1000
        )
        self.add_item(self.price_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Speichere die neuen Preise
        global preise
        preise[self.category_name] = self.price_input.value
        save_prices(preise)
        
        print(f"📝 Preise für {self.category_name} geändert von {interaction.user}")
        await interaction.response.send_message(
            f"✅ Preise für **{self.category_name}** wurden erfolgreich aktualisiert!", 
            ephemeral=True
        )

# Slash Command: /edit_preise
@bot.tree.command(name="edit_preise", description="Bearbeite die Preisliste (nur für autorisierte Benutzer)")
async def edit_preise_cmd(interaction: discord.Interaction):
    print(f"📝 /edit_preise command verwendet von {interaction.user}")
    
    # Vereinfachte Berechtigung-Prüfung: Nur Administratoren dürfen bearbeiten
    print(f"🔍 User: {interaction.user}, Guild: {interaction.guild}")
    print(f"🔍 User Guild Permissions: {interaction.user.guild_permissions}")
    
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung, die Preise zu bearbeiten. Nur Server-Administratoren können diese Funktion verwenden.", 
            ephemeral=True
        )
        return
    
    print(f"✅ Administrator {interaction.user} darf Preise bearbeiten")
    
    # Erstelle erweiterte Edit-View
    view = EditMainView(interaction.guild.id)
    
    await interaction.response.send_message(
        "🛠️ **Bot Einstellungen bearbeiten**\nWähle eine Kategorie aus, um die Einstellungen zu bearbeiten:",
        view=view,
        ephemeral=True
    )

# Slash Command: /clear
@bot.tree.command(name="clear", description="Lösche eine bestimmte Anzahl von Nachrichten (nur für Administratoren)")
async def clear_cmd(interaction: discord.Interaction, amount: int):
    print(f"🗑️ /clear command verwendet von {interaction.user} für {amount} Nachrichten")
    
    # Prüfe ob der User Administrator-Rechte hat
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung, Nachrichten zu löschen. Nur Administratoren können diesen Befehl verwenden.", 
            ephemeral=True
        )
        return
    
    # Prüfe ob die Anzahl gültig ist
    if amount < 1 or amount > 100:
        await interaction.response.send_message(
            "❌ Bitte gib eine Anzahl zwischen 1 und 100 an.", 
            ephemeral=True
        )
        return
    
    # Prüfe ob der Bot die nötigen Berechtigungen hat
    bot_permissions = interaction.channel.permissions_for(interaction.guild.me)
    if not bot_permissions.manage_messages:
        await interaction.response.send_message(
            "❌ Ich habe keine Berechtigung, Nachrichten in diesem Kanal zu löschen.", 
            ephemeral=True
        )
        return
    
    try:
        # Erst antworten (damit die Interaction nicht mit gelöscht wird)
        await interaction.response.send_message(
            f"🗑️ Lösche bis zu {amount} Nachrichten...",
            ephemeral=True
        )
        
        # Dann Nachrichten löschen
        deleted = await interaction.channel.purge(limit=amount)
        
        print(f"✅ {len(deleted)} Nachrichten gelöscht von {interaction.user}")
        
        # Erfolgreiche Löschung bestätigen
        await interaction.followup.send(
            f"✅ {len(deleted)} Nachrichten erfolgreich gelöscht!",
            ephemeral=True
        )
        
    except discord.Forbidden:
        # Versuche erst eine Antwort zu senden, falls noch nicht geantwortet
        try:
            await interaction.response.send_message(
                "❌ Ich habe keine Berechtigung, Nachrichten zu löschen.", 
                ephemeral=True
            )
        except:
            await interaction.followup.send(
                "❌ Ich habe keine Berechtigung, Nachrichten zu löschen.", 
                ephemeral=True
            )
    except discord.HTTPException as e:
        try:
            await interaction.response.send_message(
                f"❌ Fehler beim Löschen der Nachrichten: {str(e)}", 
                ephemeral=True
            )
        except:
            await interaction.followup.send(
                f"❌ Fehler beim Löschen der Nachrichten: {str(e)}", 
                ephemeral=True
            )
    except Exception as e:
        print(f"❌ Unerwarteter Fehler bei /clear: {e}")
        try:
            await interaction.response.send_message(
                "❌ Ein unerwarteter Fehler ist aufgetreten.", 
                ephemeral=True
            )
        except:
            await interaction.followup.send(
                "❌ Ein unerwarteter Fehler ist aufgetreten.", 
                ephemeral=True
            )


# Review Modal
class ReviewModal(Modal):
    def __init__(self, user, rating):
        super().__init__(title=f"⭐ {rating} Sterne Bewertung")
        self.user = user
        self.rating = rating
        
        self.review_text = TextInput(
            label="Deine Bewertung (optional)",
            placeholder="Erzähle anderen von deiner Erfahrung...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )
        self.add_item(self.review_text)
    
    async def on_submit(self, interaction: discord.Interaction):
        await post_review(interaction, self.user, self.rating, self.review_text.value)

# Review posting function
async def post_review(interaction: discord.Interaction, user, rating, review_text):
    review_channel = interaction.guild.get_channel(1413668548399726602)
    if not review_channel:
        await interaction.response.send_message("❌ Review-Kanal nicht gefunden.", ephemeral=True)
        return
    
    stars = "⭐" * rating
    
    embed = discord.Embed(
        title="📝 Neue Kundenbewertung",
        description=f"**Kunde:** {user.mention}\n**Bewertung:** {stars} ({rating}/5 Sterne)",
        color=0xffd700
    )
    
    if review_text.strip():
        embed.add_field(name="Kommentar", value=f'"{review_text}"', inline=False)
    else:
        embed.add_field(name="Kommentar", value="*Keine zusätzlichen Kommentare*", inline=False)
    
    embed.set_footer(text=f"Haze Visuals • {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    
    await review_channel.send(embed=embed)
    await interaction.response.send_message("✅ Vielen Dank für deine Bewertung!", ephemeral=True)
    print(f"📝 Review gepostet: {user} - {rating} Sterne")
    
    # Log review submission
    ticket_channel = interaction.channel
    if ticket_channel:
        await log_ticket_event(interaction.guild, "reviewed", user, ticket_channel.name, f"{rating} Sterne - {review_text[:50] if review_text else 'Keine Kommentare'}...")
    
    # Auto-close ticket after review is submitted
    ticket_channel = interaction.channel
    try:
        # Send final message before closing
        final_embed = discord.Embed(
            title="🎉 Ticket abgeschlossen",
            description="Vielen Dank für deine Bewertung! Dieses Ticket wird automatisch geschlossen.",
            color=0x00ff00
        )
        
        await ticket_channel.send(embed=final_embed)
        
        # Free up any appointments associated with this ticket before closing
        freed_appointments = await free_ticket_appointments(ticket_channel.name)
        if freed_appointments > 0:
            print(f"📅 {freed_appointments} Termin(e) für {ticket_channel.name} nach Review automatisch freigegeben")
        
        # Delete the ticket channel after a short delay
        import asyncio
        await asyncio.sleep(3)  # 3 second delay so user can see the final message
        await ticket_channel.delete(reason=f"Ticket automatisch geschlossen nach Review von {user}")
        print(f"🔒 Ticket {ticket_channel.name} automatisch geschlossen nach Review")
        
    except Exception as e:
        print(f"❌ Fehler beim automatischen Schließen des Tickets: {e}")

# New clothing order system
async def start_clothing_selection(ticket_channel, user):
    try:
        embed = discord.Embed(
            title="👕 Clothing Bestellung",
            description="Was für eine Art von Clothing benötigst du?\n\n🎨 **Custom** - Individuelle Designs nach deinen Vorstellungen\n✅ **Finished** - Vorgefertigte Pakete sofort verfügbar\n❓ **Fragen** - Allgemeine Fragen und Beratung",
            color=0x3498db
        )
        
        # Clothing type selection buttons
        clothing_view = View(timeout=None)
        options = [
            ("🎨 Custom", "custom"),
            ("✅ Finished", "finished"), 
            ("❓ Fragen", "fragen")
        ]
        
        def create_option_callback(option_type):
            async def option_callback(option_interaction):
                if option_interaction.user != user:
                    await option_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
                    return
                
                if option_type == "custom":
                    await start_custom_order(ticket_channel, user, option_interaction)
                elif option_type == "finished":
                    await show_finished_info(ticket_channel, user, option_interaction)
                elif option_type == "fragen":
                    await show_questions_info(ticket_channel, user, option_interaction)
            return option_callback
        
        for label, option_type in options:
            button = Button(label=label, style=discord.ButtonStyle.primary)
            button.callback = create_option_callback(option_type)
            clothing_view.add_item(button)
        
        # Try to send with banner, fall back to without if it fails
        try:
            banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
            await ticket_channel.send(embed=embed, view=clothing_view, file=banner_file)
        except Exception as banner_error:
            print(f"⚠️ Banner loading failed, sending without banner: {banner_error}")
            await ticket_channel.send(embed=embed, view=clothing_view)
            
    except Exception as e:
        print(f"❌ Error in start_clothing_selection: {e}")
        # Fallback simple message
        simple_embed = discord.Embed(
            title="👕 Clothing Bestellung",
            description="**Wähle deine Option:**\n\n🎨 Custom - Individuelle Designs\n✅ Finished - Vorgefertigte Pakete\n❓ Fragen - Beratung\n\nBitte kontaktiere unser Team für weitere Hilfe.",
            color=0x3498db
        )
        await ticket_channel.send(embed=simple_embed)

# Custom Order Modal for collecting colors and faction
class CustomOrderModal(Modal):
    def __init__(self, ticket_channel, user):
        super().__init__(title="🎨 Custom Clothing Details")
        self.ticket_channel = ticket_channel
        self.user = user
        
        self.main_color = TextInput(
            label="Main Farbe",
            placeholder="z.B. Schwarz, Rot, Blau...",
            required=True,
            max_length=50
        )
        
        self.secondary_color = TextInput(
            label="Secundäre Farbe", 
            placeholder="z.B. Weiß, Gold, Silber...",
            required=True,
            max_length=50
        )
        
        self.faction_name = TextInput(
            label="Fraktions Name",
            placeholder="z.B. LSPD, Ballas, Vagos...",
            required=True,
            max_length=50
        )
        
        self.add_item(self.main_color)
        self.add_item(self.secondary_color)
        self.add_item(self.faction_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        order_data = {
            "main_color": self.main_color.value,
            "secondary_color": self.secondary_color.value,
            "faction": self.faction_name.value
        }
        
        await interaction.response.send_message("✅ Details erfasst!", ephemeral=True)
        await show_product_selection(self.ticket_channel, self.user, order_data)

# Functions for handling different clothing options
async def start_custom_order(ticket_channel, user, interaction):
    modal = CustomOrderModal(ticket_channel, user)
    await interaction.response.send_modal(modal)

async def show_finished_info(ticket_channel, user, interaction):
    embed = discord.Embed(
        title="✅ Finished Clothing",
        description="Was benötigst du?\n\n📦 **Fertige Pakete** - Vorgefertigte Clothing-Sets\n🛠️ **Support** - Hilfe und Beratung",
        color=0x2ecc71
    )
    
    finished_view = View(timeout=None)
    finished_options = [
        ("📦 Fertige Pakete", "finished_packages"),
        ("🛠️ Support", "finished_support")
    ]
    
    def create_finished_callback(option_type):
        async def finished_callback(finished_interaction):
            if finished_interaction.user != user:
                await finished_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
                return
            
            if option_type == "finished_packages":
                await start_finished_package_order(ticket_channel, user, finished_interaction)
            elif option_type == "finished_support":
                await show_finished_support_info(ticket_channel, user, finished_interaction)
        return finished_callback
    
    for label, option_type in finished_options:
        button = Button(label=label, style=discord.ButtonStyle.primary)
        button.callback = create_finished_callback(option_type)
        finished_view.add_item(button)
    
    await ticket_channel.send(embed=embed, view=finished_view)
    await interaction.response.send_message("✅ Optionen angezeigt!", ephemeral=True)

async def show_questions_info(ticket_channel, user, interaction):
    embed = discord.Embed(
        title="❓ Fragen",
        description="Du hast Fragen zu unserem Clothing Service.\n\nUnser Team wird sich bei dir melden und alle deine Fragen beantworten!",
        color=0xe67e22
    )
    
    await ticket_channel.send(embed=embed)
    await interaction.response.send_message("✅ Anfrage gesendet!", ephemeral=True)

# Finished Package Modal for collecting faction and package choice
class FinishedPackageModal(Modal):
    def __init__(self, ticket_channel, user):
        super().__init__(title="📦 Fertige Pakete Details")
        self.ticket_channel = ticket_channel
        self.user = user
        
        self.faction = TextInput(
            label="Which fraktion",
            placeholder="z.B. LSPD, Ballas, Vagos...",
            required=True,
            max_length=50
        )
        
        self.package = TextInput(
            label="Welches Paket",
            placeholder="z.B. Standard, Premium, VIP...",
            required=True,
            max_length=50
        )
        
        self.add_item(self.faction)
        self.add_item(self.package)
    
    async def on_submit(self, interaction: discord.Interaction):
        order_data = {
            "faction": self.faction.value,
            "package": self.package.value,
            "type": "finished_package"
        }
        
        await interaction.response.send_message("✅ Details erfasst!", ephemeral=True)
        await show_finished_package_selection(self.ticket_channel, self.user, order_data)

async def start_finished_package_order(ticket_channel, user, interaction):
    modal = FinishedPackageModal(ticket_channel, user)
    await interaction.response.send_modal(modal)

async def show_finished_support_info(ticket_channel, user, interaction):
    embed = discord.Embed(
        title="🛠️ Support",
        description="Du benötigst Hilfe bei fertigen Paketen.\n\nUnser Team wird sich bei dir melden und dir weiterhelfen!",
        color=0xe67e22
    )
    
    await ticket_channel.send(embed=embed)
    await interaction.response.send_message("✅ Support-Anfrage gesendet!", ephemeral=True)

async def show_finished_package_selection(ticket_channel, user, order_data):
    embed = discord.Embed(
        title="📦 Paket Auswahl",
        description=f"**Details:**\n**Fraktion:** {order_data['faction']}\n**Gewünschtes Paket:** {order_data['package']}\n\nWähle das gewünschte Produkt:",
        color=0x9b59b6
    )
    product_view = View(timeout=None)
    products = [
        ("✅ Fertiges Paket - 10€", "fertiges_paket", 10),
        ("📦 Premium Paket - 15€", "premium_paket", 15),
        ("⭐ VIP Paket - 25€", "vip_paket", 25)
    ]
    
    def create_finished_product_callback(product_type, price):
        async def finished_product_callback(product_interaction):
            if product_interaction.user != user:
                await product_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
                return
            
            order_data['product'] = product_type
            order_data['base_price'] = price
            await show_discount_choice(ticket_channel, user, order_data, product_interaction)
        return finished_product_callback
    
    for label, product_type, price in products:
        button = Button(label=label, style=discord.ButtonStyle.secondary)
        button.callback = create_finished_product_callback(product_type, price)
        product_view.add_item(button)
    
    await ticket_channel.send(embed=embed, view=product_view)

# Product selection after custom details
async def show_product_selection(ticket_channel, user, order_data):
    embed = discord.Embed(
        title="📦 Produkt Auswahl",
        description=f"**Details:**\n**Main Farbe:** {order_data['main_color']}\n**Secundäre Farbe:** {order_data['secondary_color']}\n**Fraktion:** {order_data['faction']}\n\nWähle das gewünschte Produkt:",
        color=0x9b59b6
    )
    product_view = View(timeout=None)
    products = [
        ("🎁 Custom Paket - 20€", "custom_paket", 20),
        ("⚡ Custom einzeln - 5€", "custom_einzeln", 5),
        ("🦺 Custom Weste - 10€", "custom_weste", 10)
    ]
    
    def create_product_callback(product_type, price):
        async def product_callback(product_interaction):
            if product_interaction.user != user:
                await product_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
                return
            
            order_data['product'] = product_type
            order_data['base_price'] = price
            await show_discount_choice(ticket_channel, user, order_data, product_interaction)
        return product_callback
    
    for label, product_type, price in products:
        button = Button(label=label, style=discord.ButtonStyle.secondary)
        button.callback = create_product_callback(product_type, price)
        product_view.add_item(button)
    
    await ticket_channel.send(embed=embed, view=product_view)

# Discount Code Modal
class DiscountCodeModal(Modal):
    def __init__(self, ticket_channel, user, order_data):
        super().__init__(title="🎟️ Discount Code")
        self.ticket_channel = ticket_channel
        self.user = user
        self.order_data = order_data
        
        self.discount_code = TextInput(
            label="Discount Code (optional)",
            placeholder="z.B. HAZE",
            required=False,
            max_length=20
        )
        self.add_item(self.discount_code)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Load discount codes from JSON file
        valid_codes = load_discount_codes()
        
        # Check if code was entered
        if not self.discount_code.value.strip():
            # No code entered, continue without discount
            self.order_data['discount'] = 0
            self.order_data['discount_text'] = ""
            await interaction.response.send_message("✅ Weiter ohne Code!", ephemeral=True)
            await show_delivery_options(self.ticket_channel, self.user, self.order_data)
            return
        
        # Check if code is valid
        if self.discount_code.value.upper() in valid_codes:
            discount = valid_codes[self.discount_code.value.upper()]
            discount_text = f"\n✅ **Discount Code:** {self.discount_code.value.upper()} (-{int(discount*100)}%)"
            
            self.order_data['discount'] = discount
            self.order_data['discount_text'] = discount_text
            
            await interaction.response.send_message("✅ Code erfolgreich angewendet!", ephemeral=True)
            await show_delivery_options(self.ticket_channel, self.user, self.order_data)
        else:
            # Invalid code - give options
            await show_invalid_code_options(self.ticket_channel, self.user, self.order_data, self.discount_code.value, interaction)

# Invalid discount code options
async def show_invalid_code_options(ticket_channel, user, order_data, invalid_code, interaction):
    embed = discord.Embed(
        title="❌ Ungültiger Discount Code",
        description=f"Der Code **{invalid_code}** ist nicht gültig.\n\nWas möchtest du tun?",
        color=0xe74c3c
    )
    # Options view
    options_view = View(timeout=None)
    
    # Try new code button
    retry_button = Button(label="🔄 Neuen Code eingeben", style=discord.ButtonStyle.primary)
    async def retry_callback(retry_interaction):
        if retry_interaction.user != user:
            await retry_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
            return
        
        # Show discount input modal again
        modal = DiscountCodeModal(ticket_channel, user, order_data)
        await retry_interaction.response.send_modal(modal)
    
    retry_button.callback = retry_callback
    
    # Continue without code button
    continue_button = Button(label="➡️ Ohne Code fortfahren", style=discord.ButtonStyle.secondary)
    async def continue_callback(continue_interaction):
        if continue_interaction.user != user:
            await continue_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
            return
        
        # Continue without discount
        order_data['discount'] = 0
        order_data['discount_text'] = ""
        
        await continue_interaction.response.send_message("✅ Ohne Discount Code fortfahren!", ephemeral=True)
        await show_delivery_options(ticket_channel, user, order_data)
    
    continue_button.callback = continue_callback
    
    options_view.add_item(retry_button)
    options_view.add_item(continue_button)
    
    await ticket_channel.send(embed=embed, view=options_view)
    await interaction.response.send_message("❌ Code ungültig - wähle eine Option!", ephemeral=True)

# Show discount choice - optional selection
async def show_discount_choice(ticket_channel, user, order_data, interaction):
    embed = discord.Embed(
        title="🎟️ Discount Code",
        description="Möchtest du einen Discount Code verwenden?",
        color=0x9b59b6
    )
    embed.add_field(
        name="💡 Hinweis",
        value="Falls du einen exklusiven Rabattcode hast, kannst du ihn hier eingeben.\n\nFalls nicht, kannst du einfach ohne Code fortfahren.",
        inline=False
    )
    
    choice_view = View(timeout=None)
    
    # Use discount code button
    use_code_button = Button(label="🎟️ Discount Code verwenden", style=discord.ButtonStyle.primary)
    async def use_code_callback(code_interaction):
        if code_interaction.user != user:
            await code_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
            return
        
        modal = DiscountCodeModal(ticket_channel, user, order_data)
        await code_interaction.response.send_modal(modal)
    
    use_code_button.callback = use_code_callback
    
    # Skip discount code button
    skip_code_button = Button(label="➡️ Ohne Code fortfahren", style=discord.ButtonStyle.secondary)
    async def skip_code_callback(skip_interaction):
        if skip_interaction.user != user:
            await skip_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
            return
        
        # Continue without discount
        order_data['discount'] = 0
        order_data['discount_text'] = ""
        
        await skip_interaction.response.send_message("✅ Weiter ohne Code!", ephemeral=True)
        await show_delivery_options(ticket_channel, user, order_data)
    
    skip_code_button.callback = skip_code_callback
    
    choice_view.add_item(use_code_button)
    choice_view.add_item(skip_code_button)
    
    await ticket_channel.send(embed=embed, view=choice_view)
    await interaction.response.send_message("✅ Produkt ausgewählt!", ephemeral=True)

# Show discount code input modal (when user chooses to use a code)
async def show_discount_input(ticket_channel, user, order_data, interaction):
    modal = DiscountCodeModal(ticket_channel, user, order_data)
    await interaction.response.send_modal(modal)

# Show options when invalid discount code is entered
async def show_invalid_code_options(ticket_channel, user, order_data, invalid_code, interaction):
    embed = discord.Embed(
        title="❌ Ungültiger Discount Code",
        description=f"Der Code **{invalid_code}** ist nicht gültig.\n\nWas möchtest du tun?",
        color=0xe74c3c
    )
    
    invalid_code_view = View(timeout=None)
    
    # Try again button
    try_again_button = Button(label="🔄 Neuen Code eingeben", style=discord.ButtonStyle.primary)
    
    async def try_again_callback(try_interaction):
        if try_interaction.user != user:
            await try_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
            return
        
        modal = DiscountCodeModal(ticket_channel, user, order_data)
        await try_interaction.response.send_modal(modal)
    
    try_again_button.callback = try_again_callback
    
    # Continue without code button
    continue_button = Button(label="➡️ Ohne Code weiter", style=discord.ButtonStyle.secondary)
    
    async def continue_callback(continue_interaction):
        if continue_interaction.user != user:
            await continue_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
            return
        
        # Continue without discount
        order_data['discount'] = 0
        order_data['discount_text'] = ""
        
        await continue_interaction.response.send_message("✅ Weiter ohne Discount Code!", ephemeral=True)
        await show_delivery_options(ticket_channel, user, order_data)
    
    continue_button.callback = continue_callback
    
    invalid_code_view.add_item(try_again_button)
    invalid_code_view.add_item(continue_button)
    
    await ticket_channel.send(embed=embed, view=invalid_code_view)
    await interaction.response.send_message("❌ Code ungültig - bitte wähle eine Option!", ephemeral=True)

# Delivery options selection
async def show_delivery_options(ticket_channel, user, order_data):
    base_price = order_data['base_price']
    discount = order_data.get('discount', 0)
    discounted_price = base_price * (1 - discount)
    
    embed = discord.Embed(
        title="🚚 Delivery Optionen",
        description=f"**Aktueller Preis:** {discounted_price:.2f}€{order_data.get('discount_text', '')}\n\nHast du zusätzliche Anfragen für die Lieferung?",
        color=0x3498db
    )
    
    delivery_view = View(timeout=None)
    delivery_options = [
        ("📦 Standard Delivery", "standard", 0),
        ("⚡ Fast Delivery (+25%)", "fast", 0.25),
        ("🚀 Extra Fast Delivery (+50%)", "extra_fast", 0.50)
    ]
    
    def create_delivery_callback(delivery_type, multiplier):
        async def delivery_callback(delivery_interaction):
            if delivery_interaction.user != user:
                await delivery_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
                return
            
            order_data['delivery_type'] = delivery_type
            order_data['delivery_multiplier'] = multiplier
            await show_final_payment(ticket_channel, user, order_data, delivery_interaction)
        return delivery_callback
    
    for label, delivery_type, multiplier in delivery_options:
        button = Button(label=label, style=discord.ButtonStyle.primary)
        button.callback = create_delivery_callback(delivery_type, multiplier)
        delivery_view.add_item(button)
    
    await ticket_channel.send(embed=embed, view=delivery_view)

# Final payment selection with total calculation
async def show_final_payment(ticket_channel, user, order_data, interaction):
    # Calculate final price
    base_price = order_data['base_price']
    discount = order_data.get('discount', 0)
    delivery_multiplier = order_data.get('delivery_multiplier', 0)
    
    discounted_price = base_price * (1 - discount)
    delivery_cost = discounted_price * delivery_multiplier
    final_price = discounted_price + delivery_cost
    
    # Build order summary based on order type
    if order_data.get('type') == 'finished_package':
        summary = f"""**📋 Bestellzusammenfassung:**
**Fraktion:** {order_data['faction']}
**Paket:** {order_data['package']}
**Produkt:** {order_data['product']}

**💰 Preisberechnung:**
Grundpreis: {base_price:.2f}€{order_data.get('discount_text', '')}
Delivery: +{delivery_cost:.2f}€
**Gesamtpreis: {final_price:.2f}€**

Wähle deine Zahlungsmethode:"""
    else:
        summary = f"""**📋 Bestellzusammenfassung:**
**Main Farbe:** {order_data['main_color']}
**Secundäre Farbe:** {order_data['secondary_color']}
**Fraktion:** {order_data['faction']}
**Produkt:** {order_data['product']}

**💰 Preisberechnung:**
Grundpreis: {base_price:.2f}€{order_data.get('discount_text', '')}
Delivery: +{delivery_cost:.2f}€
**Gesamtpreis: {final_price:.2f}€**

Wähle deine Zahlungsmethode:"""
    
    embed = discord.Embed(
        title="💳 Zahlung",
        description=summary,
        color=0x27ae60
    )
    embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    
    payment_view = View(timeout=None)
    
    # Hole Server-Konfiguration für aktivierte Zahlungsmethoden
    server_config = get_server_config(interaction.guild.id)
    payment_config = server_config.get("payment", {})
    
    # Standard-Zahlungsmethoden (nur aktivierte)
    payment_options = []
    
    if payment_config.get("paypal_enabled", True):
        payment_options.append(("💙 PayPal", "paypal"))
    
    if payment_config.get("bank_enabled", True):
        payment_options.append(("🏦 Bank Transfer", "bank"))
    
    if payment_config.get("paysafe_enabled", True):
        payment_options.append(("💳 Paysafecard", "paysafe"))
    
    # Neue Zahlungsmethoden hinzufügen (falls aktiviert)
    if payment_config.get("tebex_enabled", False):
        payment_options.append(("🛒 Tebex Code", "tebex"))
    
    if payment_config.get("amazon_enabled", False):
        payment_options.append(("📦 Amazon Giftcard", "amazon"))
    
    if payment_config.get("netflix_enabled", False):
        payment_options.append(("🎬 Netflix Card", "netflix"))
    
    if payment_config.get("creditcard_enabled", False):
        payment_options.append(("💳 Credit Card", "creditcard"))
    
    if payment_config.get("enhanced_crypto_enabled", False):
        # Bitcoin hinzufügen falls Wallet konfiguriert
        btc_wallet = payment_config.get("crypto", {}).get("bitcoin_wallet", "")
        if btc_wallet and len(btc_wallet) > 20:
            payment_options.append(("₿ Bitcoin", "bitcoin"))
        
        # Ethereum hinzufügen falls Wallet konfiguriert
        eth_wallet = payment_config.get("crypto", {}).get("ethereum_wallet", "")
        if eth_wallet and len(eth_wallet) > 20:
            payment_options.append(("⚡ Ethereum", "ethereum"))
    
    def create_final_payment_callback(payment_type):
        async def final_payment_callback(payment_interaction):
            if payment_interaction.user != user:
                await payment_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
                return
            
            await handle_final_payment(payment_interaction, ticket_channel, user, order_data, final_price, payment_type)
        return final_payment_callback
    
    for label, payment_type in payment_options:
        button = Button(label=label, style=discord.ButtonStyle.success)
        button.callback = create_final_payment_callback(payment_type)
        payment_view.add_item(button)
    
    banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    await ticket_channel.send(embed=embed, view=payment_view, file=banner_file)
    await interaction.response.send_message("✅ Bestellung zusammengefasst!", ephemeral=True)

# Handle final payment selection
async def handle_final_payment(interaction, ticket_channel, user, order_data, final_price, payment_type):
    # Create purpose of use (except for Paysafecard)
    if payment_type != "paysafe":
        from datetime import datetime
        import pytz
        berlin_tz = pytz.timezone('Europe/Berlin')
        current_date = datetime.now(berlin_tz).strftime('%d.%m.%Y')
        
        product_name = order_data.get('product', 'Unknown Package')
        purpose_of_use = f"({user.name}) Haze Visuals Clothing {product_name} - {current_date}"
    
    if payment_type == "paypal":
        embed = discord.Embed(
            title="💙 PayPal Zahlung",
            description=f"**PayPal Email:** `hazeevisuals@gmail.com`\n**Betrag:** {final_price:.2f}€\n**Verwendungszweck:** `{purpose_of_use}`\n\n✅ Bitte sende deine Zahlung an diese Email-Adresse mit dem Verwendungszweck.",
            color=0x0070ba
        )
        embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        
        # Add payment confirmation button
        payment_confirm_view = View(timeout=None)
        confirm_button = Button(label="✅ Zahlung gesendet", style=discord.ButtonStyle.success)
        
        async def payment_sent_callback(confirm_interaction):
            if confirm_interaction.user != user:
                await confirm_interaction.response.send_message("❌ Nur der Kunde kann die Zahlung bestätigen.", ephemeral=True)
                return
            await show_payment_loading(ticket_channel, user, final_price, "PayPal", confirm_interaction)
        
        confirm_button.callback = payment_sent_callback
        payment_confirm_view.add_item(confirm_button)
        
        banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        await ticket_channel.send(embed=embed, view=payment_confirm_view, file=banner_file)
        
        # Safe interaction response with timeout handling
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("✅ PayPal Details gesendet!", ephemeral=True)
            else:
                await interaction.followup.send("✅ PayPal Details gesendet!", ephemeral=True)
        except discord.errors.NotFound:
            print("⚠️ Interaction expired - PayPal details sent successfully anyway")
        
    elif payment_type == "bank":
        # Hole Bank-Details aus Server-Konfiguration
        server_config = get_server_config(interaction.guild.id)
        payment_config = server_config.get("payment", {})
        bank_name = payment_config.get("account_holder", "Unser Team") 
        bank_iban = payment_config.get("iban", "Wird vom Team mitgeteilt")
        bank_bic = payment_config.get("bic", "Wird vom Team mitgeteilt")
        
        if bank_iban != "Wird vom Team mitgeteilt":
            # Vollständige Bank-Details anzeigen
            embed = discord.Embed(
                title="🏦 Bank Transfer",
                description=f"**Empfänger:** {bank_name}\n**IBAN:** `{bank_iban}`\n**BIC:** `{bank_bic}`\n**Betrag:** {final_price:.2f}€\n**Verwendungszweck:** `{purpose_of_use}`\n\n⚠️ **Wichtig:** Verwende den oben genannten Verwendungszweck bei der Überweisung!",
                color=0x34495e
            )
        else:
            # Fallback wenn keine Bank-Details konfiguriert
            embed = discord.Embed(
                title="🏦 Bank Transfer",
                description=f"**Betrag:** {final_price:.2f}€\n**Verwendungszweck:** `{purpose_of_use}`\n\n💬 Unser Support-Team wird sich bezüglich der Bankdaten bei dir melden.\n\n⚠️ **Wichtig:** Verwende den oben genannten Verwendungszweck bei der Überweisung!",
                color=0x34495e
            )
        embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        
        # Ping HV | Team role with purpose info (nur wenn Bank-Details nicht konfiguriert)
        if bank_iban == "Wird vom Team mitgeteilt":
            hv_team_role = discord.utils.get(interaction.guild.roles, name="HV | Team")
            ping_text = f"{hv_team_role.mention if hv_team_role else '@HV | Team'} - Bank Transfer Anfrage von {user.mention}\n**Verwendungszweck:** `{purpose_of_use}`"
            await ticket_channel.send(ping_text)
        
        # Add payment confirmation button
        payment_confirm_view = View(timeout=None)
        confirm_button = Button(label="✅ Zahlung gesendet", style=discord.ButtonStyle.success)
        
        async def bank_payment_sent_callback(confirm_interaction):
            if confirm_interaction.user != user:
                await confirm_interaction.response.send_message("❌ Nur der Kunde kann die Zahlung bestätigen.", ephemeral=True)
                return
            await show_payment_loading(ticket_channel, user, final_price, "Bank Transfer", confirm_interaction)
        
        confirm_button.callback = bank_payment_sent_callback
        payment_confirm_view.add_item(confirm_button)
        
        banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        await ticket_channel.send(embed=embed, view=payment_confirm_view, file=banner_file)
        
        # Safe interaction response with timeout handling
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("✅ Team benachrichtigt!", ephemeral=True)
            else:
                await interaction.followup.send("✅ Team benachrichtigt!", ephemeral=True)
        except discord.errors.NotFound:
            print("⚠️ Interaction expired - Team notification sent successfully anyway")
        
    elif payment_type == "paysafe":
        modal = FinalPaysafecardModal(ticket_channel, final_price, user)
        await interaction.response.send_modal(modal)
        
    # Neue Zahlungsmethoden
    elif payment_type == "tebex":
        await handle_tebex_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use)
    elif payment_type == "amazon":
        await handle_amazon_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use)
    elif payment_type == "netflix":
        await handle_netflix_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use)
    elif payment_type == "creditcard":
        await handle_creditcard_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use)
    elif payment_type == "bitcoin":
        await handle_bitcoin_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use)
    elif payment_type == "ethereum":
        await handle_ethereum_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use)

# Updated Paysafecard Modal for final payment
class FinalPaysafecardModal(Modal):
    def __init__(self, ticket_channel, final_price, user):
        super().__init__(title="💳 Paysafecard Payment")
        self.ticket_channel = ticket_channel
        self.final_price = final_price
        self.user = user
        
        self.paysafe_code = TextInput(
            label="Paysafecard Code",
            placeholder="Gib deinen Paysafecard Code ein...",
            required=True,
            max_length=20
        )
        self.add_item(self.paysafe_code)
    
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💳 Paysafecard Code erhalten",
            description=f"**Code:** `{self.paysafe_code.value}`\n**Betrag:** {self.final_price:.2f}€\n\n✅ Dein Paysafecard Code wurde an unser Team weitergeleitet.",
            color=0x00ff00
        )
        embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        
        # Add payment confirmation button
        payment_confirm_view = View(timeout=None)
        confirm_button = Button(label="✅ Code gesendet", style=discord.ButtonStyle.success)
        
        async def paysafe_sent_callback(confirm_interaction):
            if confirm_interaction.user != self.user:
                await confirm_interaction.response.send_message("❌ Nur der Kunde kann die Zahlung bestätigen.", ephemeral=True)
                return
            await show_payment_loading(self.ticket_channel, self.user, self.final_price, "Paysafecard", confirm_interaction)
        
        confirm_button.callback = paysafe_sent_callback
        payment_confirm_view.add_item(confirm_button)
        
        banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        await self.ticket_channel.send(embed=embed, view=payment_confirm_view, file=banner_file)
        await interaction.response.send_message("✅ Paysafecard Code übermittelt!", ephemeral=True)

# Payment loading state
async def show_payment_loading(ticket_channel, user, final_price, payment_method, interaction):
    embed = discord.Embed(
        title="⏳ Zahlung wird verarbeitet",
        description=f"**Zahlungsmethode:** {payment_method}\n**Betrag:** {final_price:.2f}€\n\n🔄 Unser Team überprüft deine Zahlung...\n\n⏳ Bitte warte, bis ein Teammitglied deine Zahlung bestätigt hat.",
        color=0xf39c12
    )
    embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    
    banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    await ticket_channel.send(embed=embed, file=banner_file)
    await interaction.response.send_message("✅ Zahlung gemeldet!", ephemeral=True)
    
    # Log payment confirmation
    await log_ticket_event(ticket_channel.guild, "payment_confirmed", user, ticket_channel.name, f"{payment_method} - {final_price:.2f}€")

# Ticket logging system
async def log_ticket_event(guild, event_type, user, ticket_name, details=""):
    log_channel = guild.get_channel(1413668472059199558)
    if not log_channel:
        return
    
    # Event type specific formatting
    if event_type == "opened":
        embed = discord.Embed(
            title="🎫 Ticket Geöffnet",
            description=f"**User:** {user.mention}\n**Ticket:** {ticket_name}\n**Zeit:** <t:{int(datetime.now().timestamp())}:F>",
            color=0x00ff00
        )
        embed.add_field(name="Details", value=details if details else "Neues Ticket erstellt", inline=False)
        
    elif event_type == "claimed":
        embed = discord.Embed(
            title="🏷️ Ticket Claimed",
            description=f"**Teammitglied:** {user.mention}\n**Ticket:** {ticket_name}\n**Zeit:** <t:{int(datetime.now().timestamp())}:F>",
            color=0x3498db
        )
        embed.add_field(name="Status", value="Ticket wurde vom Team übernommen", inline=False)
        
    elif event_type == "payment_confirmed":
        embed = discord.Embed(
            title="💰 Zahlung Bestätigt",
            description=f"**Kunde:** {user.mention}\n**Ticket:** {ticket_name}\n**Zeit:** <t:{int(datetime.now().timestamp())}:F>",
            color=0xf39c12
        )
        embed.add_field(name="Zahlungsdetails", value=details, inline=False)
        
    elif event_type == "finished":
        embed = discord.Embed(
            title="✅ Ticket Abgeschlossen",
            description=f"**Teammitglied:** {user.mention}\n**Ticket:** {ticket_name}\n**Zeit:** <t:{int(datetime.now().timestamp())}:F>",
            color=0x2ecc71
        )
        embed.add_field(name="Status", value="Bestellung abgeschlossen - Review System gestartet", inline=False)
        
    elif event_type == "reviewed":
        embed = discord.Embed(
            title="⭐ Review Erhalten",
            description=f"**Kunde:** {user.mention}\n**Ticket:** {ticket_name}\n**Zeit:** <t:{int(datetime.now().timestamp())}:F>",
            color=0xffd700
        )
        embed.add_field(name="Bewertung", value=details, inline=False)
    
    embed.set_footer(text="Haze Visuals • Ticket System")
    await log_channel.send(embed=embed)

# Appointment Management Functions
def load_appointments():
    """Load booked appointments from JSON file"""
    try:
        with open('appointments.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print("❌ Fehler beim Laden der Termine")
        return {}

def save_appointments(appointments):
    """Save appointments to JSON file"""
    try:
        with open('appointments.json', 'w') as f:
            json.dump(appointments, f, indent=4)
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Termine: {e}")

def get_available_time_slots(ticket_created_at=None):
    """Get available appointment slots for the next 7 days"""
    from datetime import datetime, timedelta
    import pytz
    
    berlin_tz = pytz.timezone('Europe/Berlin')
    now = datetime.now(berlin_tz)
    
    # Check 24-hour delay requirement
    if ticket_created_at:
        min_booking_time = ticket_created_at + timedelta(hours=24)
        if now < min_booking_time:
            return {}  # No slots available yet
    
    available_slots = {}
    booked_appointments = load_appointments()
    
    # Generate slots for next 7 days
    for day_offset in range(7):
        date = now + timedelta(days=day_offset)
        date_str = date.strftime('%Y-%m-%d')
        weekday = date.strftime('%A')  # Monday, Tuesday, etc.
        
        # Generate time slots from 18:00 to 22:00 (every 30 minutes)
        day_slots = []
        for hour in range(18, 22):
            for minute in [0, 30]:
                # Create datetime object for this specific slot
                slot_datetime = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # Skip if this slot is in the past (add 30 minute buffer for booking)
                if slot_datetime <= now + timedelta(minutes=30):
                    continue
                
                slot_time = f"{hour:02d}:{minute:02d}"
                slot_key = f"{date_str}_{slot_time}"
                
                # Check if slot is available (not booked)
                if slot_key not in booked_appointments:
                    day_slots.append({
                        'time': slot_time,
                        'slot_key': slot_key,
                        'display': f"{weekday} {date.strftime('%d.%m')} - {slot_time}"
                    })
        
        if day_slots:
            available_slots[date_str] = {
                'weekday': weekday,
                'date_display': date.strftime('%d.%m.%Y'),
                'slots': day_slots
            }
    
    return available_slots

async def book_appointment(slot_key, user_id, user_name, ticket_name, bot):
    """Book an appointment slot"""
    appointments = load_appointments()
    
    # Check if slot is still available
    if slot_key in appointments:
        # Log unavailable appointment attempt
        await log_unavailable_appointment(slot_key, user_name, bot)
        return False, "Dieser Termin ist bereits vergeben."
    
    # Book the slot
    appointments[slot_key] = {
        'user_id': user_id,
        'user_name': user_name,
        'ticket_name': ticket_name,
        'booked_at': datetime.now().isoformat()
    }
    
    save_appointments(appointments)
    
    # Update calendar display after booking
    try:
        await update_calendar_display()
        print(f"📅 Kalender nach Terminbuchung aktualisiert")
    except Exception as e:
        print(f"❌ Fehler beim Aktualisieren des Kalenders nach Buchung: {e}")
    
    return True, "Termin erfolgreich gebucht!"

async def free_ticket_appointments(ticket_name):
    """Free up all appointments associated with a specific ticket"""
    try:
        appointments = load_appointments()
        appointments_freed = 0
        
        # Find and remove appointments for this ticket
        appointments_to_remove = []
        for slot_key, appointment_data in appointments.items():
            if appointment_data.get('ticket_name') == ticket_name:
                appointments_to_remove.append(slot_key)
        
        # Remove the appointments
        for slot_key in appointments_to_remove:
            del appointments[slot_key]
            appointments_freed += 1
        
        if appointments_freed > 0:
            # Save updated appointments
            save_appointments(appointments)
            
            # Update calendar display
            await update_calendar_display()
            print(f"📅 {appointments_freed} Termin(e) für Ticket {ticket_name} freigegeben")
            
        return appointments_freed
        
    except Exception as e:
        print(f"❌ Fehler beim Freigeben der Termine für Ticket {ticket_name}: {e}")
        return 0

async def clear_all_appointments():
    """Clear all booked appointments and update calendar"""
    try:
        appointments = load_appointments()
        total_cleared = len(appointments)
        
        # Clear all appointments
        appointments.clear()
        
        # Save empty appointments file
        save_appointments(appointments)
        
        # Update calendar display
        await update_calendar_display()
        
        print(f"📅 Alle {total_cleared} Termine wurden gelöscht")
        return total_cleared
        
    except Exception as e:
        print(f"❌ Fehler beim Löschen aller Termine: {e}")
        return 0

# Ticket form data storage functions
def load_ticket_forms():
    """Load ticket form data from JSON file"""
    try:
        with open('ticket_forms.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print("❌ Fehler beim Laden der Ticket-Formulardaten")
        return {}

def save_ticket_forms(ticket_forms):
    """Save ticket form data to JSON file"""
    try:
        with open('ticket_forms.json', 'w', encoding='utf-8') as f:
            json.dump(ticket_forms, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Ticket-Formulardaten: {e}")

def store_ticket_form_data(ticket_name, form_data):
    """Store form data for a specific ticket"""
    ticket_forms = load_ticket_forms()
    ticket_forms[ticket_name] = form_data
    save_ticket_forms(ticket_forms)

def get_ticket_form_data(ticket_name):
    """Get form data for a specific ticket"""
    ticket_forms = load_ticket_forms()
    return ticket_forms.get(ticket_name, {})

# Open tickets counter functions
async def count_open_tickets(guild):
    """Count all open tickets in the guild"""
    open_count = 0
    
    # Define ticket categories to check
    ticket_category_ids = [
        1413669641062055976,  # Bestellung
        1413669733957636156,  # Support
        1413892803162800178,  # Paid
    ]
    
    for category_id in ticket_category_ids:
        category = guild.get_channel(category_id)
        if category:
            for channel in category.channels:
                if isinstance(channel, discord.TextChannel):
                    # Count channels that look like tickets
                    if any(prefix in channel.name for prefix in ['clothing-', 'support-', 'bug-', 'vorschlag-', 'ticket-']):
                        open_count += 1
    
    return open_count

async def delayed_counter_update(guild, delay_seconds):
    """Update ticket counter after a delay to prevent rate limiting"""
    import asyncio
    await asyncio.sleep(delay_seconds)
    await update_ticket_counter_channel(guild)

async def update_ticket_counter_channel(guild):
    """Update the ticket counter channel name with rate limiting protection"""
    try:
        # Rate limiting protection: only update every 5 seconds per guild
        import time
        current_time = time.time()
        guild_id = guild.id
        
        # Check if we updated this guild's counter recently
        if hasattr(update_ticket_counter_channel, 'last_updates'):
            if guild_id in update_ticket_counter_channel.last_updates:
                if current_time - update_ticket_counter_channel.last_updates[guild_id] < 5:
                    print(f"⚠️ Skipping counter update for guild {guild.name} - too recent")
                    return
        else:
            update_ticket_counter_channel.last_updates = {}
        
        # Find the ticket counter channel in category 1413674754409238549
        counter_category = guild.get_channel(1413674754409238549)
        if not counter_category:
            print("❌ Ticket counter category not found")
            return
        
        # Look for existing counter channel (voice channel)
        counter_channel = None
        for channel in counter_category.channels:
            if isinstance(channel, discord.VoiceChannel) and "offene tickets" in channel.name.lower():
                counter_channel = channel
                break
        
        # Count open tickets
        open_count = await count_open_tickets(guild)
        
        # Update channel name
        new_name = f"📊 Offene Tickets: {open_count}"
        
        if counter_channel:
            if counter_channel.name != new_name:
                try:
                    await counter_channel.edit(name=new_name)
                    print(f"📊 Ticket counter updated: {new_name}")
                    # Record successful update time
                    update_ticket_counter_channel.last_updates[guild_id] = current_time
                except discord.errors.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        print(f"⚠️ Ticket counter update rate limited - backing off")
                        # Set longer backoff time on rate limit
                        update_ticket_counter_channel.last_updates[guild_id] = current_time + 30
                    else:
                        print(f"❌ Error updating ticket counter: {e}")
        else:
            # If channel doesn't exist, create it
            await create_ticket_counter_channel(guild)
    
    except Exception as e:
        print(f"❌ Error updating ticket counter: {e}")

async def create_ticket_counter_channel(guild):
    """Create the ticket counter voice channel"""
    try:
        # Get the category
        counter_category = guild.get_channel(1413674754409238549)
        if not counter_category:
            print("❌ Category 1413674754409238549 not found")
            return
        
        # Count current open tickets
        open_count = await count_open_tickets(guild)
        
        # Set up permissions for voice channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True)
        }
        
        # Add specific roles with view permissions
        role_names = ["Customer", "Verified"]
        for role_name in role_names:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, connect=False)
        
        # Create the voice channel
        channel_name = f"📊 Offene Tickets: {open_count}"
        counter_channel = await guild.create_voice_channel(
            channel_name,
            category=counter_category,
            overwrites=overwrites
        )
        
        print(f"✅ Ticket counter voice channel created: {channel_name}")
        
        return counter_channel
        
    except Exception as e:
        print(f"❌ Error creating ticket counter voice channel: {e}")
        return None

async def ensure_ticket_counter_channel_exists(guild):
    """Ensure the ticket counter channel exists, create it if not"""
    try:
        # Find the ticket counter channel in category 1413674754409238549
        counter_category = guild.get_channel(1413674754409238549)
        if not counter_category:
            print("❌ Ticket counter category not found")
            return
        
        # Look for existing counter channel
        counter_channel = None
        for channel in counter_category.channels:
            if isinstance(channel, discord.TextChannel) and "offene-tickets" in channel.name.lower():
                counter_channel = channel
                break
        
        # If channel doesn't exist, create it
        if not counter_channel:
            await create_ticket_counter_channel(guild)
        else:
            # Update existing channel to ensure correct count
            await update_ticket_counter_channel(guild)
            
    except Exception as e:
        print(f"❌ Error ensuring ticket counter channel exists: {e}")

async def update_member_counter_channel(guild):
    """Update the member counter channel name with rate limiting protection"""
    try:
        # Rate limiting protection: only update every 5 seconds per guild
        import time
        current_time = time.time()
        guild_id = guild.id
        
        # Check if we updated this guild's counter recently
        if hasattr(update_member_counter_channel, 'last_updates'):
            if guild_id in update_member_counter_channel.last_updates:
                if current_time - update_member_counter_channel.last_updates[guild_id] < 5:
                    return
        else:
            update_member_counter_channel.last_updates = {}
        
        # Find the member counter channel in category 1413674754409238549
        counter_category = guild.get_channel(1413674754409238549)
        if not counter_category:
            return
        
        # Look for existing counter channel (voice channel)
        counter_channel = None
        for channel in counter_category.channels:
            if isinstance(channel, discord.VoiceChannel) and "mitglieder" in channel.name.lower():
                counter_channel = channel
                break
        
        # Count members (excluding bots)
        member_count = len([m for m in guild.members if not m.bot])
        
        # Update channel name
        new_name = f"👥 Mitglieder: {member_count}"
        
        if counter_channel:
            if counter_channel.name != new_name:
                try:
                    await counter_channel.edit(name=new_name)
                    print(f"👥 Member counter updated: {new_name}")
                    # Record successful update time
                    update_member_counter_channel.last_updates[guild_id] = current_time
                except discord.errors.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        print(f"⚠️ Member counter update rate limited - backing off")
                        # Set longer backoff time on rate limit
                        update_member_counter_channel.last_updates[guild_id] = current_time + 30
                    else:
                        print(f"❌ Error updating member counter: {e}")
        else:
            # If channel doesn't exist, create it
            await create_member_counter_channel(guild)
    
    except Exception as e:
        print(f"❌ Error updating member counter: {e}")

async def create_member_counter_channel(guild):
    """Create the member counter voice channel"""
    try:
        # Get the category
        counter_category = guild.get_channel(1413674754409238549)
        if not counter_category:
            print("❌ Category 1413674754409238549 not found")
            return
        
        # Count current members (excluding bots)
        member_count = len([m for m in guild.members if not m.bot])
        
        # Set up permissions for voice channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True)
        }
        
        # Add specific roles with view permissions
        role_names = ["Customer", "Verified"]
        for role_name in role_names:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, connect=False)
        
        # Create the voice channel
        channel_name = f"👥 Mitglieder: {member_count}"
        counter_channel = await guild.create_voice_channel(
            channel_name,
            category=counter_category,
            overwrites=overwrites
        )
        
        print(f"✅ Member counter voice channel created: {channel_name}")
        
        return counter_channel
        
    except Exception as e:
        print(f"❌ Error creating member counter voice channel: {e}")
        return None

async def ensure_member_counter_channel_exists(guild):
    """Ensure the member counter channel exists, create it if not"""
    try:
        # Find the member counter channel in category 1413674754409238549
        counter_category = guild.get_channel(1413674754409238549)
        if not counter_category:
            return
        
        # Look for existing counter channel
        counter_channel = None
        for channel in counter_category.channels:
            if isinstance(channel, discord.VoiceChannel) and "mitglieder" in channel.name.lower():
                counter_channel = channel
                break
        
        # If channel doesn't exist, create it
        if not counter_channel:
            await create_member_counter_channel(guild)
        else:
            # Update existing channel to ensure correct count
            await update_member_counter_channel(guild)
            
    except Exception as e:
        print(f"❌ Error ensuring member counter channel exists: {e}")

# Server configuration storage functions
def load_server_configs():
    """Load server configurations from JSON file"""
    try:
        with open('server_configs.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print("❌ Fehler beim Laden der Server-Konfigurationen")
        return {}

def save_server_configs(server_configs):
    """Save server configurations to JSON file"""
    try:
        with open('server_configs.json', 'w', encoding='utf-8') as f:
            json.dump(server_configs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Server-Konfigurationen: {e}")

def get_server_config(guild_id):
    """Get configuration for a specific server"""
    server_configs = load_server_configs()
    return server_configs.get(str(guild_id), get_default_config())

def save_server_config(guild_id, config):
    """Save configuration for a specific server"""
    server_configs = load_server_configs()
    server_configs[str(guild_id)] = config
    save_server_configs(server_configs)

def get_server_banner_url(guild_id):
    """Get custom banner URL for server, fallback to default"""
    server_config = get_server_config(guild_id)
    
    # Check in ticket_customization first (new structure)
    banner_url = server_config.get("ticket_customization", {}).get("banner_url")
    if banner_url:
        return banner_url
    
    # Check in branding (alternative location)
    banner_url = server_config.get("branding", {}).get("banner_url") 
    if banner_url:
        return banner_url
    
    # Default banner
    return "attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif"

def set_server_banner_url(guild_id, banner_url):
    """Set custom banner URL for server"""
    server_config = get_server_config(guild_id)
    
    # Ensure ticket_customization exists
    if "ticket_customization" not in server_config:
        server_config["ticket_customization"] = {}
    
    server_config["ticket_customization"]["banner_url"] = banner_url
    save_server_config(guild_id, server_config)
    print(f"🖼️ Banner URL updated for guild {guild_id}: {banner_url}")
    
def get_banner_filename_from_url(banner_url):
    """Extract filename from banner URL for attachment reference"""
    if banner_url.startswith("http"):
        # Online image, use as direct URL
        return None
    else:
        # Local file, extract filename
        return banner_url.split("/")[-1]

async def send_embed_with_banner(channel, embed, view=None, guild_id=None):
    """Send embed with custom banner for the server"""
    try:
        if guild_id is None and hasattr(channel, 'guild'):
            guild_id = channel.guild.id
        
        if guild_id:
            banner_url = get_server_banner_url(guild_id)
            
            if banner_url.startswith("http"):
                # Online image - set as embed image
                embed.set_image(url=banner_url)
                await channel.send(embed=embed, view=view)
            else:
                # Local file - send as attachment
                filename = get_banner_filename_from_url(banner_url)
                if filename:
                    embed.set_image(url=f"attachment://{filename}")
                    banner_file = discord.File(banner_url, filename=filename)
                    await channel.send(embed=embed, view=view, file=banner_file)
                else:
                    # Fallback without banner
                    await channel.send(embed=embed, view=view)
        else:
            # No guild context, send without banner
            await channel.send(embed=embed, view=view)
            
    except Exception as e:
        print(f"⚠️ Banner loading failed, sending without banner: {e}")
        # Remove image from embed if it was set
        if embed.image and embed.image.url:
            embed.set_image(url="")
        await channel.send(embed=embed, view=view)

def get_default_config():
    """Get default configuration for new servers"""
    return {
        "categories": {
            "open": 1413669641062055976,
            "claimed": 1413669733957636156,
            "paid": 1413892803162800178,
            "finished": 1413893025620299837
        },
        "ticket_types": [
            "Bestellung",
            "Support", 
            "Bug Report",
            "Vorschlag",
            "Bewerbung"
        ],
        "custom_categories": {},
        "ticket_customization": {
            "panel_title": "🎫 TICKET SYSTEM",
            "panel_description": """╔═══════════════════════════════════════╗
║              🌪️ HAZE VISUALS 🌪️              ║
║            ✨ Support Center ✨            ║
╚═══════════════════════════════════════╝

📞 **Brauchst du Hilfe?**
Klicke auf einen der Buttons unten, um ein Ticket zu erstellen:

🛒 **Bestellung** - Für Aufträge und Kaufanfragen
🛠️ **Support** - Allgemeine Hilfe und Fragen  
🐛 **Bug Report** - Probleme melden
💡 **Vorschlag** - Ideen und Feedback
📋 **Bewerbung** - Team-Bewerbungen

⚡ **Hinweise:**
• Ein Ticket pro Person zur gleichen Zeit
• Unser Team antwortet so schnell wie möglich
• Verwende die richtige Kategorie für dein Anliegen""",
            "banner_url": "attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757177441437.gif",
            "footer_text": "Haze Visuals • Ticket System"
        },
        "commands_enabled": {
            "preise": True,
            "edit_preise": True,
            "adddiscount": True,
            "discountremove": True,
            "discountlist": True,
            "clear": True,
            "terminerefresh": True,
            "ticket_panel": True,
            "setup": True
        },
        "features": {
            "payment_system": True,
            "calendar_system": True,
            "review_system": True,
            "discount_codes": True,
            "welcome_messages": True,
            "leave_messages": True,
            "music_bot": False
        },
        "ticket_names": {
            "Bestellung": "clothing-{username}",
            "Support": "support-{username}",
            "Bug Report": "bug-{username}",
            "Vorschlag": "vorschlag-{username}",
            "Bewerbung": "ticket-{username}"
        },
        "channels": {
            "welcome_channel": 1413665493545390090,
            "leave_channel": 1413665534930587650,
            "calendar_channel": 1413668409853345792,
            "review_channel": 1413668548399726602,
            "music_channel": None
        },
        "roles": {
            "staff_role": "HV | Team",
            "admin_role": "HV | Leitung",
            "customer_role": "Customer"
        },
        "messages": {
            "welcome_message": "Willkommen {mention} auf {server}. Viel Spaß !",
            "leave_message": "{username} hat uns verlassen"
        },
        "music_bot": {
            "enabled": False,
            "channel_id": None,
            "playlist_url": "",
            "volume": 50,
            "auto_play": True
        }
    }

# Ticket Ping System Functions
def load_pending_tickets():
    """Load pending tickets from JSON file"""
    try:
        with open('pending_tickets.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print("❌ Fehler beim Laden der pending tickets")
        return {}

def save_pending_tickets(tickets):
    """Save pending tickets to JSON file"""
    try:
        with open('pending_tickets.json', 'w') as f:
            json.dump(tickets, f, indent=4)
    except Exception as e:
        print(f"❌ Fehler beim Speichern der pending tickets: {e}")

async def store_ticket_for_ping_system(ticket_id, user_id, created_at):
    """Store ticket for 30-minute ping system"""
    pending_tickets = load_pending_tickets()
    
    ticket_key = str(ticket_id)
    pending_tickets[ticket_key] = {
        'user_id': user_id,
        'created_at': created_at.isoformat(),
        'needs_ping': True,
        'pinged': False
    }
    
    save_pending_tickets(pending_tickets)

async def mark_ticket_responded(ticket_id):
    """Mark ticket as responded to by team"""
    pending_tickets = load_pending_tickets()
    ticket_key = str(ticket_id)
    
    if ticket_key in pending_tickets:
        pending_tickets[ticket_key]['needs_ping'] = False
        save_pending_tickets(pending_tickets)

async def check_and_ping_unresponded_tickets(bot):
    """Check for tickets that need team ping after 30 minutes"""
    from datetime import datetime, timedelta
    import pytz
    
    pending_tickets = load_pending_tickets()
    berlin_tz = pytz.timezone('Europe/Berlin')
    now = datetime.now(berlin_tz)
    
    tickets_to_remove = []
    
    for ticket_id, ticket_data in pending_tickets.items():
        if not ticket_data['needs_ping'] or ticket_data['pinged']:
            continue
            
        # Parse creation time
        try:
            created_at = datetime.fromisoformat(ticket_data['created_at'])
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=berlin_tz)
            
            # Check if 30 minutes have passed
            time_diff = now - created_at
            if time_diff >= timedelta(minutes=30):
                # Find the ticket channel
                try:
                    ticket_channel = bot.get_channel(int(ticket_id))
                    if ticket_channel:
                        # Get HV | Team role
                        hv_team_role = discord.utils.get(ticket_channel.guild.roles, name="HV | Team")
                        if hv_team_role:
                            embed = discord.Embed(
                                title="⏰ Team-Erinnerung",
                                description=f"{hv_team_role.mention}\n\nDieses Ticket wartet seit **30 Minuten** auf eine Antwort vom Team.",
                                color=0xff9500,
                                timestamp=now
                            )
                            embed.set_footer(text="Haze Visuals • Automatische Erinnerung")
                            
                            await ticket_channel.send(embed=embed)
                            
                            # Mark as pinged
                            pending_tickets[ticket_id]['pinged'] = True
                            print(f"📨 Team gepingt für Ticket {ticket_channel.name}")
                    else:
                        # Ticket doesn't exist anymore, remove from tracking
                        tickets_to_remove.append(ticket_id)
                except Exception as e:
                    print(f"❌ Fehler beim Pingen für Ticket {ticket_id}: {e}")
                    tickets_to_remove.append(ticket_id)
        except Exception as e:
            print(f"❌ Fehler beim Parsen der Zeit für Ticket {ticket_id}: {e}")
            tickets_to_remove.append(ticket_id)
    
    # Remove non-existent tickets
    for ticket_id in tickets_to_remove:
        if ticket_id in pending_tickets:
            del pending_tickets[ticket_id]
    
    save_pending_tickets(pending_tickets)

async def log_unavailable_appointment(slot_key, user_name, bot):
    """Log when a user tries to book an unavailable appointment"""
    try:
        log_channel = bot.get_channel(1413668409853345792)
        if log_channel:
            # Parse slot info
            date_part, time_part = slot_key.split('_')
            from datetime import datetime
            date_obj = datetime.strptime(date_part, '%Y-%m-%d')
            weekday = date_obj.strftime('%A')
            date_display = date_obj.strftime('%d.%m.%Y')
            
            embed = discord.Embed(
                title="❌ Termin bereits vergeben",
                description=f"**{user_name}** wollte einen bereits vergebenen Termin buchen:\n\n📅 **{weekday}, {date_display}**\n🕐 **{time_part} Uhr**",
                color=0xff6b6b,
                timestamp=datetime.now()
            )
            embed.set_footer(text="Haze Visuals • Terminverwaltung")
            
            await log_channel.send(embed=embed)
    except Exception as e:
        print(f"❌ Fehler beim Loggen des unavailable appointments: {e}")

# Appointment Selection UI
async def show_appointment_selection(ticket_channel, user, ticket_name, ticket_created_at=None):
    """Show appointment selection interface to customer"""
    # Check 24-hour delay
    if ticket_created_at:
        from datetime import datetime, timedelta
        import pytz
        berlin_tz = pytz.timezone('Europe/Berlin')
        now = datetime.now(berlin_tz)
        min_booking_time = ticket_created_at + timedelta(hours=24)
        
        if now < min_booking_time:
            time_remaining = min_booking_time - now
            hours_remaining = int(time_remaining.total_seconds() // 3600)
            minutes_remaining = int((time_remaining.total_seconds() % 3600) // 60)
            
            embed = discord.Embed(
                title="⏰ Termine noch nicht verfügbar",
                description=f"Hallo {user.mention}!\n\nDu kannst Termine erst **24 Stunden** nach der Ticket-Erstellung buchen.\n\n🕐 **Noch zu warten:** {hours_remaining}h {minutes_remaining}m\n\nUnser Team wird dich benachrichtigen, sobald du einen Termin buchen kannst!",
                color=0xffa500
            )
            embed.set_footer(text="Haze Visuals • Terminbuchung")
            await ticket_channel.send(embed=embed)
            return
    
    embed = discord.Embed(
        title="📅 Termin buchen",
        description=f"Hallo {user.mention}! 🎉\n\nDeine Zahlung wurde bestätigt! Jetzt kannst du einen Termin für die Bearbeitung deiner Bestellung buchen.\n\n⏰ **Verfügbare Zeiten:** Täglich 18:00 - 22:00 Uhr (Berlin Zeit)\n🕐 **Dauer:** 30 Minuten pro Termin",
        color=0x00ff00
    )
    # Get available slots
    available_slots = get_available_time_slots(ticket_created_at)
    
    if not available_slots:
        embed.add_field(
            name="❌ Keine Termine verfügbar", 
            value="Aktuell sind keine Termine in den nächsten 7 Tagen verfügbar. Bitte kontaktiere das Team.", 
            inline=False
        )
        await ticket_channel.send(embed=embed)
        return
    
    # Create day selection view
    day_view = AppointmentDayView(user, ticket_name, available_slots)
    
    await ticket_channel.send(embed=embed, view=day_view)

class AppointmentDayView(View):
    """View for selecting appointment day"""
    def __init__(self, user, ticket_name, available_slots):
        super().__init__(timeout=3600)  # 1 hour timeout
        self.user = user
        self.ticket_name = ticket_name
        self.available_slots = available_slots
        
        # Add day selection buttons (max 5 buttons per row)
        for date_str, day_info in list(available_slots.items())[:7]:  # Show max 7 days
            button = Button(
                label=f"{day_info['weekday']} {day_info['date_display']}", 
                style=discord.ButtonStyle.primary,
                custom_id=f"day_{date_str}"
            )
            button.callback = self.day_selected
            self.add_item(button)
    
    async def day_selected(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Nur der Ticket-Ersteller kann einen Termin buchen.", ephemeral=True)
            return
        
        # Extract selected date from custom_id
        selected_date = interaction.data['custom_id'].replace('day_', '')
        
        if selected_date not in self.available_slots:
            await interaction.response.send_message("❌ Dieser Tag ist nicht mehr verfügbar.", ephemeral=True)
            return
        
        # Show time slots for selected day
        await show_time_slot_selection(interaction, self.user, self.ticket_name, selected_date, self.available_slots[selected_date])

async def show_time_slot_selection(interaction, user, ticket_name, selected_date, day_info):
    """Show time slot selection for the selected day"""
    embed = discord.Embed(
        title=f"🕐 Uhrzeit wählen - {day_info['weekday']} {day_info['date_display']}",
        description="Wähle deine gewünschte Uhrzeit:",
        color=0x00ff00
    )
    # Create time slot view
    time_view = AppointmentTimeView(user, ticket_name, selected_date, day_info['slots'])
    
    await interaction.response.send_message(embed=embed, view=time_view, ephemeral=True)

class AppointmentTimeView(View):
    """View for selecting appointment time"""
    def __init__(self, user, ticket_name, selected_date, slots):
        super().__init__(timeout=3600)  # 1 hour timeout
        self.user = user
        self.ticket_name = ticket_name
        self.selected_date = selected_date
        
        # Add time slot buttons
        for slot in slots:
            button = Button(
                label=slot['time'], 
                style=discord.ButtonStyle.success,
                custom_id=f"time_{slot['slot_key']}"
            )
            button.callback = self.time_selected
            self.add_item(button)
    
    async def time_selected(self, interaction: discord.Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ Nur der Ticket-Ersteller kann einen Termin buchen.", ephemeral=True)
            return
        
        # Extract slot key from custom_id
        slot_key = interaction.data['custom_id'].replace('time_', '')
        
        # Book the appointment
        bot = interaction.client
        success, message = await book_appointment(slot_key, self.user.id, self.user.display_name, self.ticket_name, bot)
        
        if success:
            # Parse slot info for display
            date_part, time_part = slot_key.split('_')
            from datetime import datetime
            date_obj = datetime.strptime(date_part, '%Y-%m-%d')
            weekday = date_obj.strftime('%A')
            date_display = date_obj.strftime('%d.%m.%Y')
            
            embed = discord.Embed(
                title="✅ Termin gebucht!",
                description=f"Dein Termin wurde erfolgreich gebucht:\n\n📅 **{weekday}, {date_display}**\n🕐 **{time_part} Uhr (Berlin Zeit)**\n\nUnser Team wird sich zur vereinbarten Zeit um deine Bestellung kümmern!",
                color=0x00ff00
            )
            embed.set_footer(text="Haze Visuals • Terminbuchung")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Send confirmation and design preparation message to the ticket channel
            channel_embed = discord.Embed(
                title="📅 Termin bestätigt",
                description=f"{self.user.mention} hat einen Termin gebucht:\n\n📅 **{weekday}, {date_display}**\n🕐 **{time_part} Uhr (Berlin Zeit)**",
                color=0x00ff00
            )
            await interaction.followup.send(embed=channel_embed)
            
            # Design preparation message
            prep_embed = discord.Embed(
                title="🎨 Vorbereitung für den Designtermin",
                description=f"Dein Termin ist am **{weekday}, {date_display} um {time_part} Uhr**.\n\nBitte mache dir bis dahin Gedanken wie deine Kleidung aussehen soll und sammele ggf. Beispiele die du dem Designer im Design Prozess direkt zeigen kannst, damit es keine unnötigen Verzögerungen gibt.\n\n**Wenn du ein Logo hast, sende es bitte ins Ticket rein!**",
                color=0x9b59b6
            )
            prep_embed.set_footer(text="Haze Visuals • Design Vorbereitung")
            await interaction.followup.send(embed=prep_embed)
            
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)

# Discount Code Management Functions
def load_discount_codes():
    """Load discount codes from JSON file with enhanced structure"""
    try:
        with open('discount_codes.json', 'r') as f:
            codes = json.load(f)
            
            # Migrate old format to new format if needed
            migrated_codes = {}
            for code, value in codes.items():
                if isinstance(value, dict):
                    # Already new format
                    migrated_codes[code] = value
                else:
                    # Old format - migrate to new structure
                    migrated_codes[code] = {
                        "type": "percentage",
                        "value": value,
                        "max_uses": -1,  # -1 = unlimited, 1 = single use
                        "current_uses": 0,
                        "used_by": [],
                        "auto_delete": False,  # Auto-delete after use
                        "created_at": int(datetime.now().timestamp()),
                        "description": f"{int(value * 100)}% Rabatt"
                    }
            
            # Save migrated format
            if codes != migrated_codes:
                save_discount_codes(migrated_codes)
                print("✅ Discount codes migrated to new format")
            
            return migrated_codes
            
    except FileNotFoundError:
        # Return default codes in new format
        default_codes = {
            "FIJI": {
                "type": "percentage",
                "value": 0.10,
                "max_uses": -1,
                "current_uses": 0,
                "used_by": [],
                "auto_delete": False,
                "created_at": int(datetime.now().timestamp()),
                "description": "10% Rabatt"
            },
            "CATLEEN": {
                "type": "percentage", 
                "value": 0.10,
                "max_uses": -1,
                "current_uses": 0,
                "used_by": [],
                "auto_delete": False,
                "created_at": int(datetime.now().timestamp()),
                "description": "10% Rabatt"
            },
            "STILLES": {
                "type": "percentage",
                "value": 0.10,
                "max_uses": -1,
                "current_uses": 0,
                "used_by": [],
                "auto_delete": False,
                "created_at": int(datetime.now().timestamp()),
                "description": "10% Rabatt"
            }
        }
        save_discount_codes(default_codes)
        return default_codes
    except json.JSONDecodeError:
        print("❌ Fehler beim Laden der Discount Codes")
        return {}

def save_discount_codes(codes):
    """Save discount codes to JSON file with enhanced structure"""
    try:
        with open('discount_codes.json', 'w', encoding='utf-8') as f:
            json.dump(codes, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Discount Codes: {e}")

def validate_and_use_discount_code(code, user_id, price_str):
    """Validate discount code and calculate discount. Returns (success, new_price, discount_text, message)"""
    try:
        # Parse price (remove € and convert to float)
        base_price = float(price_str.replace('€', '').replace(',', '.'))
        
        discount_codes = load_discount_codes()
        code_upper = code.upper()
        
        if code_upper not in discount_codes:
            return False, price_str, "", f"❌ Discount Code '{code}' nicht gefunden."
        
        code_data = discount_codes[code_upper]
        
        # Check if code has usage limit
        if code_data.get("max_uses", -1) != -1:  # Not unlimited
            if code_data.get("current_uses", 0) >= code_data.get("max_uses", 0):
                return False, price_str, "", f"❌ Discount Code '{code}' wurde bereits verwendet und ist nicht mehr gültig."
            
            # Check if user already used this code
            if user_id in code_data.get("used_by", []):
                return False, price_str, "", f"❌ Du hast den Discount Code '{code}' bereits verwendet."
        
        # Calculate discount
        discount_type = code_data.get("type", "percentage")
        discount_value = code_data.get("value", 0)
        
        if discount_type == "percentage":
            discount_amount = base_price * discount_value
            new_price = base_price - discount_amount
            discount_text = f" (- {int(discount_value * 100)}%: -{discount_amount:.2f}€)"
        else:  # fixed amount
            discount_amount = min(discount_value, base_price)  # Don't exceed price
            new_price = base_price - discount_amount
            discount_text = f" (- {discount_amount:.2f}€)"
        
        # Ensure price doesn't go negative
        new_price = max(0, new_price)
        
        # Update usage statistics
        code_data["current_uses"] = code_data.get("current_uses", 0) + 1
        if user_id not in code_data.get("used_by", []):
            code_data.setdefault("used_by", []).append(user_id)
        
        # Check if code should be auto-deleted after use
        auto_delete = code_data.get("auto_delete", False)
        is_single_use = code_data.get("max_uses", -1) == 1
        
        success_message = f"✅ Discount Code '{code}' angewendet!"
        
        if auto_delete and is_single_use:
            # Delete the code completely after first use
            del discount_codes[code_upper]
            success_message += f" (Code wurde automatisch gelöscht)"
            print(f"🗑️ Auto-delete: Code '{code_upper}' wurde nach Verwendung gelöscht")
        elif is_single_use:
            success_message += f" (Einmalig verwendbar - jetzt deaktiviert)"
        
        # Save updated codes
        save_discount_codes(discount_codes)
        
        return True, f"{new_price:.2f}€", discount_text, success_message
        
    except ValueError:
        return False, price_str, "", "❌ Fehler beim Berechnen des Rabatts."
    except Exception as e:
        print(f"❌ Fehler bei Discount Code Validierung: {e}")
        return False, price_str, "", "❌ Ein Fehler ist aufgetreten."


# Discount code management functions

# Slash Command: /adddiscount
@bot.tree.command(name="adddiscount", description="Füge einen neuen Discount Code hinzu (nur für Administratoren)")
async def add_discount_cmd(interaction: discord.Interaction, code: str, percentage: int):
    # Check admin permissions
    if not interaction.user.guild_permissions.administrator:
        hv_team_role = discord.utils.get(interaction.guild.roles, name="HV | Team")
        hv_leitung_role = discord.utils.get(interaction.guild.roles, name="HV | Leitung")
        
        if not (hv_team_role in interaction.user.roles or hv_leitung_role in interaction.user.roles):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung für diesen Befehl. Nur Administratoren und HV Team können Discount Codes verwalten.", 
                ephemeral=True
            )
            return
    
    # Validate percentage
    if percentage < 1 or percentage > 100:
        await interaction.response.send_message(
            "❌ Der Prozentsatz muss zwischen 1 und 100 liegen.", 
            ephemeral=True
        )
        return
    
    # Load existing codes
    discount_codes = load_discount_codes()
    
    # Add new code
    code_upper = code.upper()
    discount_value = percentage / 100
    discount_codes[code_upper] = discount_value
    
    # Save updated codes
    save_discount_codes(discount_codes)
    
    await interaction.response.send_message(
        f"✅ Discount Code `{code_upper}` wurde hinzugefügt mit {percentage}% Rabatt!", 
        ephemeral=True
    )
    print(f"➕ Discount Code hinzugefügt: {code_upper} - {percentage}% von {interaction.user}")

# Slash Command: /discountremove
@bot.tree.command(name="discountremove", description="Entferne einen Discount Code (nur für Administratoren)")
async def remove_discount_cmd(interaction: discord.Interaction, code: str):
    # Check admin permissions
    if not interaction.user.guild_permissions.administrator:
        hv_team_role = discord.utils.get(interaction.guild.roles, name="HV | Team")
        hv_leitung_role = discord.utils.get(interaction.guild.roles, name="HV | Leitung")
        
        if not (hv_team_role in interaction.user.roles or hv_leitung_role in interaction.user.roles):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung für diesen Befehl. Nur Administratoren und HV Team können Discount Codes verwalten.", 
                ephemeral=True
            )
            return
    
    # Load existing codes
    discount_codes = load_discount_codes()
    
    # Check if code exists
    code_upper = code.upper()
    if code_upper not in discount_codes:
        await interaction.response.send_message(
            f"❌ Discount Code `{code_upper}` wurde nicht gefunden.", 
            ephemeral=True
        )
        return
    
    # Remove code
    del discount_codes[code_upper]
    
    # Save updated codes
    save_discount_codes(discount_codes)
    
    await interaction.response.send_message(
        f"✅ Discount Code `{code_upper}` wurde erfolgreich entfernt!", 
        ephemeral=True
    )
    print(f"➖ Discount Code entfernt: {code_upper} von {interaction.user}")

# Slash Command: /discountlist (bonus command to view all codes)
@bot.tree.command(name="discountlist", description="Zeige alle verfügbaren Discount Codes (nur für Administratoren)")
async def list_discount_cmd(interaction: discord.Interaction):
    # Check admin permissions
    if not interaction.user.guild_permissions.administrator:
        hv_team_role = discord.utils.get(interaction.guild.roles, name="HV | Team")
        hv_leitung_role = discord.utils.get(interaction.guild.roles, name="HV | Leitung")
        
        if not (hv_team_role in interaction.user.roles or hv_leitung_role in interaction.user.roles):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung für diesen Befehl. Nur Administratoren und HV Team können Discount Codes einsehen.", 
                ephemeral=True
            )
            return
    
    # Load existing codes
    discount_codes = load_discount_codes()
    
    if not discount_codes:
        await interaction.response.send_message("📋 Keine Discount Codes vorhanden.", ephemeral=True)
        return
    
    # Create embed with all codes
    embed = discord.Embed(
        title="🎟️ Verfügbare Discount Codes",
        description="Alle aktuell verfügbaren Rabattcodes:",
        color=0x9b59b6
    )
    
    code_list = ""
    for code, discount in discount_codes.items():
        percentage = int(discount * 100)
        code_list += f"**{code}** - {percentage}% Rabatt\n"
    
    embed.add_field(name="Codes", value=code_list, inline=False)
    embed.set_footer(text="Haze Visuals • Discount System")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Ticket-System: Erstelle ein neues Ticket
async def create_ticket(interaction: discord.Interaction, ticket_type: str):
    await create_ticket_with_form(interaction, ticket_type, None)

async def create_ticket_with_form(interaction: discord.Interaction, ticket_type: str, form_data=None):
    guild = interaction.guild
    user = interaction.user
    
    # Get server configuration
    server_config = get_server_config(guild.id)
    
    # Ticket-Namen und Kategorie-IDs definieren
    ticket_configs = {
        "Bestellung": {
            "name": f"clothing-{user.name.lower()}", 
            "category_id": server_config.get("categories", {}).get("open", 1413669641062055976)
        },
        "Support": {
            "name": f"support-{user.name.lower()}", 
            "category_id": server_config.get("categories", {}).get("claimed", 1413669733957636156)
        },
        "Bug Report": {
            "name": f"bug-{user.name.lower()}", 
            "category_id": server_config.get("categories", {}).get("claimed", 1413669733957636156)
        },
        "Vorschlag": {
            "name": f"vorschlag-{user.name.lower()}", 
            "category_id": server_config.get("categories", {}).get("claimed", 1413669733957636156)
        },
        "Bewerbung": {
            "name": f"ticket-{user.name.lower()}", 
            "category_id": server_config.get("categories", {}).get("claimed", 1413669733957636156)
        }
    }
    
    config = ticket_configs.get(ticket_type)
    if not config:
        await interaction.response.send_message("❌ Unbekannter Ticket-Typ.", ephemeral=True)
        return
    
    channel_name = config["name"]
    category_id = config["category_id"]
    
    # Prüfe Ticket-Limit (maximal 10 offene Tickets pro User)
    user_tickets = []
    username_lower = user.name.lower()
    
    # Zähle alle Tickets des Users (in allen Kategorien)
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            # Prüfe auf Ticket-Pattern: ticket-typ-username oder username-status-typ
            channel_name_lower = channel.name.lower()
            if (username_lower in channel_name_lower and 
                any(pattern in channel_name_lower for pattern in ['clothing-', 'support-', 'bug-', 'vorschlag-', 'ticket-', f'-{username_lower}'])):
                user_tickets.append(channel)
    
    # Limit von 10 Tickets pro User
    if len(user_tickets) >= 10:
        ticket_list = "\n".join([f"• {ticket.mention}" for ticket in user_tickets[:5]])
        if len(user_tickets) > 5:
            ticket_list += f"\n• ... und {len(user_tickets) - 5} weitere"
        
        await interaction.response.send_message(
            f"❌ **Ticket-Limit erreicht!**\n\n"
            f"Du hast bereits {len(user_tickets)} offene Tickets (Maximum: 10).\n"
            f"Bitte schließe erst einige Tickets, bevor du neue erstellst.\n\n"
            f"**Deine offenen Tickets:**\n{ticket_list}", 
            ephemeral=True
        )
        return
    
    # Kategorie finden
    category = guild.get_channel(category_id)
    if not category:
        await interaction.response.send_message("❌ Ticket-Kategorie nicht gefunden.", ephemeral=True)
        return
    
    # WICHTIG: Sofort antworten um Timeout zu vermeiden
    await interaction.response.send_message(
        f"🔄 Erstelle dein {ticket_type} Ticket...", 
        ephemeral=True
    )
    
    # Berechtigungen für den Ticket-Kanal
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
    }
    
    # Füge Staff-Rollen hinzu (from server config)
    staff_role_names = [
        server_config["roles"]["admin_role"],
        server_config["roles"]["staff_role"],
        "Admin", 
        "Moderator"
    ]
    
    for role_name in staff_role_names:
        if role_name:  # Check if role name is not None
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
    
    try:
        # Kanal erstellen
        ticket_channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites
        )
        
        # Willkommensnachricht im Ticket
        embed = discord.Embed(
            title=f"🎫 {ticket_type} Ticket",
            description=f"Hallo {user.mention}!\n\n📋 **Ticket-Typ:** {ticket_type}\n🕐 **Erstellt:** <t:{int(interaction.created_at.timestamp())}:F>\n\n✅ Unser Team wird sich so schnell wie möglich bei dir melden!",
            color=0x00ff00
        )
        
        # Füge Formular-Daten hinzu (für Bestellungen)
        if form_data:
            form_text = "\n\n📝 **Bestelldetails:**\n"
            for key, value in form_data.items():
                form_text += f"**{key}:** {value}\n"
            embed.add_field(name="Deine Angaben", value=form_text, inline=False)
            
            # Store form data for later use (when ticket is marked as paid)
            store_ticket_form_data(channel_name, form_data)
            print(f"📋 Form data gespeichert für Ticket: {channel_name}")
        
        embed.set_footer(text="Haze Visuals • Ticket System")
        
        # Ticket Management Buttons (nur für HV | Team)
        ticket_view = View(timeout=None)
        
        claim_button = Button(label="🏷️ Claim", style=discord.ButtonStyle.success)
        paid_button = Button(label="💰 Paid", style=discord.ButtonStyle.primary)
        finished_button = Button(label="✅ Finished", style=discord.ButtonStyle.success)
        close_button = Button(label="🔒 Close", style=discord.ButtonStyle.danger)
        
        async def claim_ticket_callback(claim_interaction):
            # Prüfe HV | Team Rolle
            server_config = get_server_config(guild.id)
            staff_role_name = server_config["roles"]["staff_role"]
            hv_team_role = discord.utils.get(claim_interaction.guild.roles, name=staff_role_name)
            if hv_team_role not in claim_interaction.user.roles and not claim_interaction.user.guild_permissions.administrator:
                await claim_interaction.response.send_message("❌ Nur HV | Team kann Tickets claimen.", ephemeral=True)
                return
            
            await claim_interaction.response.send_message(f"✅ Ticket wurde von {claim_interaction.user.mention} übernommen!")
            print(f"🏷️ Ticket {channel_name} wurde von {claim_interaction.user} geclaimed")
            
            # Mark ticket as responded to
            await mark_ticket_responded(ticket_channel.id)
            
            # Log ticket claim
            await log_ticket_event(guild, "claimed", claim_interaction.user, channel_name)
        
        async def paid_ticket_callback(paid_interaction):
            # Prüfe HV | Team Rolle
            server_config = get_server_config(guild.id)
            staff_role_name = server_config["roles"]["staff_role"]
            hv_team_role = discord.utils.get(paid_interaction.guild.roles, name=staff_role_name)
            if hv_team_role not in paid_interaction.user.roles and not paid_interaction.user.guild_permissions.administrator:
                await paid_interaction.response.send_message("❌ Nur HV | Team kann Tickets als bezahlt markieren.", ephemeral=True)
                return
            
            # Get form data to extract faction name
            form_data = get_ticket_form_data(channel_name)
            faction_name = form_data.get('faction', 'unknown')
            
            # Assign Customer role to ticket creator (with enhanced error handling)
            try:
                customer_role_name = server_config["roles"]["customer_role"]
                customer_role = discord.utils.get(guild.roles, name=customer_role_name)
                if customer_role:
                    # Check if bot has permission to assign roles
                    bot_member = guild.get_member(bot.user.id)
                    if bot_member and bot_member.guild_permissions.manage_roles:
                        # Check if bot's highest role is higher than customer role
                        if bot_member.top_role > customer_role:
                            await user.add_roles(customer_role)
                            print(f"✅ Customer role assigned to {user}")
                        else:
                            print(f"⚠️ Cannot assign Customer role: Bot role is not high enough in hierarchy")
                    else:
                        print(f"⚠️ Cannot assign Customer role: Bot missing 'Manage Roles' permission")
                else:
                    print(f"❌ Customer role '{customer_role_name}' not found in guild")
            except discord.errors.Forbidden:
                print(f"⚠️ Cannot assign Customer role: Missing permissions or role hierarchy issue")
            except Exception as e:
                print(f"❌ Error assigning Customer role: {e}")
            
            # Move to paid category and rename with faction name
            paid_category_id = server_config.get("categories", {}).get("paid", 1413892803162800178)
            paid_category = guild.get_channel(paid_category_id)
            if paid_category:
                # Format: Faction-paid-username (e.g., Zakura-paid-haze219)
                new_name = f"{faction_name.lower()}-paid-{user.name.lower()}"
                await ticket_channel.edit(name=new_name, category=paid_category)
                
                response_message = f"💰 Ticket als bezahlt markiert und verschoben!\n👤 Customer Rolle zugewiesen\n🏷️ Umbenannt zu: {new_name}"
                await paid_interaction.response.send_message(response_message)
                print(f"💰 Ticket zu {new_name} umbenannt und in Paid-Kategorie verschoben")
                
                # Trigger appointment selection for the customer (need to get ticket creation time)
                # For now, we'll use None - in future we could store ticket creation time
                await show_appointment_selection(ticket_channel, user, channel_name, None)
            else:
                await paid_interaction.response.send_message("❌ Paid-Kategorie nicht gefunden.", ephemeral=True)
        
        async def finished_ticket_callback(finished_interaction):
            # Prüfe HV | Team Rolle
            server_config = get_server_config(guild.id)
            staff_role_name = server_config["roles"]["staff_role"]
            hv_team_role = discord.utils.get(finished_interaction.guild.roles, name=staff_role_name)
            if hv_team_role not in finished_interaction.user.roles and not finished_interaction.user.guild_permissions.administrator:
                await finished_interaction.response.send_message("❌ Nur HV | Team kann Tickets als fertig markieren.", ephemeral=True)
                return
            
            # Move to review category and rename
            try:
                review_category_id = server_config.get("categories", {}).get("finished", 1413893025620299837)
                review_category = guild.get_channel(review_category_id)
                if not review_category:
                    await finished_interaction.response.send_message(f"❌ Review-Kategorie ({review_category_id}) nicht gefunden.", ephemeral=True)
                    print(f"❌ Review-Kategorie mit ID {review_category_id} nicht gefunden")
                    return
                
                new_name = f"clothing-review-{user.name.lower()}"
                await ticket_channel.edit(name=new_name, category=review_category)
                
                await finished_interaction.response.send_message("✅ Ticket als fertig markiert! Review-System wird gestartet...")
                
                # Log ticket finished
                await log_ticket_event(guild, "finished", finished_interaction.user, new_name)
                
                # Start review system automatically
                await start_review_system(ticket_channel, user)
                print(f"✅ Ticket zu {new_name} umbenannt und in Review-Kategorie verschoben")
                
            except Exception as e:
                print(f"❌ Fehler beim Verschieben des Tickets: {e}")
                await finished_interaction.response.send_message("❌ Fehler beim Verschieben des Tickets.", ephemeral=True)
        
        async def close_ticket_callback(close_interaction):
            # Prüfe HV | Team Rolle
            hv_team_role = discord.utils.get(close_interaction.guild.roles, name="HV | Team")
            if hv_team_role not in close_interaction.user.roles and not close_interaction.user.guild_permissions.administrator:
                await close_interaction.response.send_message("❌ Nur HV | Team kann Tickets schließen.", ephemeral=True)
                return
            
            # Free up any appointments associated with this ticket
            freed_appointments = await free_ticket_appointments(channel_name)
            
            close_message = "🔒 Ticket wird geschlossen..."
            if freed_appointments > 0:
                close_message += f"\n📅 {freed_appointments} Termin(e) wurden automatisch freigegeben."
                
            await close_interaction.response.send_message(close_message)
            await ticket_channel.delete(reason=f"Ticket geschlossen von {close_interaction.user}")
            print(f"🔒 Ticket {channel_name} geschlossen von {close_interaction.user}")
            
            # Update ticket counter after closing ticket
            await update_ticket_counter_channel(guild)
        
        claim_button.callback = claim_ticket_callback
        paid_button.callback = paid_ticket_callback
        finished_button.callback = finished_ticket_callback
        close_button.callback = close_ticket_callback
        
        ticket_view.add_item(claim_button)
        ticket_view.add_item(paid_button)
        ticket_view.add_item(finished_button)
        ticket_view.add_item(close_button)
        
        # Send initial message and clothing selection in one optimized call
        await ticket_channel.send(embed=embed, view=ticket_view)
        
        # Add small delay to prevent rate limiting
        import asyncio
        await asyncio.sleep(1)
        
        # Start clothing selection for Bestellung tickets with better error handling
        if ticket_type == "Bestellung":
            try:
                # Create combined clothing selection embed with improved content
                clothing_embed = discord.Embed(
                    title="👕 Clothing Bestellung",
                    description="Was für eine Art von Clothing benötigst du?\n\n🎨 **Custom** - Individuelle Designs nach deinen Vorstellungen\n✅ **Finished** - Vorgefertigte Pakete sofort verfügbar\n❓ **Fragen** - Allgemeine Fragen und Beratung",
                    color=0x3498db
                )
                
                # Create clothing selection buttons
                clothing_view = View(timeout=None)
                options = [
                    ("🎨 Custom", "custom"),
                    ("✅ Finished", "finished"), 
                    ("❓ Fragen", "fragen")
                ]
                
                def create_option_callback(option_type):
                    async def option_callback(option_interaction):
                        if option_interaction.user != user:
                            await option_interaction.response.send_message("❌ Nur der Ticket-Ersteller kann antworten.", ephemeral=True)
                            return
                        
                        if option_type == "custom":
                            await start_custom_order(ticket_channel, user, option_interaction)
                        elif option_type == "finished":
                            await show_finished_info(ticket_channel, user, option_interaction)
                        elif option_type == "fragen":
                            await show_questions_info(ticket_channel, user, option_interaction)
                    return option_callback
                
                for label, option_type in options:
                    button = Button(label=label, style=discord.ButtonStyle.primary)
                    button.callback = create_option_callback(option_type)
                    clothing_view.add_item(button)
                
                # Send clothing selection (no banner to reduce API calls)
                await ticket_channel.send(embed=clothing_embed, view=clothing_view)
                print(f"✅ Optimized clothing selection started for ticket: {channel_name}")
                
            except Exception as e:
                print(f"❌ Fehler beim Starten der Clothing Selection: {e}")
                # Simple fallback without additional API calls
                print(f"⚠️ Fallback: User kann manuell mit Team chatten in {channel_name}")
        
        # Minimal delay to prevent rate limiting
        await asyncio.sleep(0.3)
        
        # Batch the final operations with enhanced error handling
        try:
            # Log ticket creation (non-blocking)
            await log_ticket_event(guild, "opened", user, channel_name, f"Ticket-Typ: {ticket_type}")
            
            # Store ticket for 30-minute ping system (non-blocking)  
            await store_ticket_for_ping_system(ticket_channel.id, user.id, interaction.created_at)
            
            # Bestätigung an den User (als followup da bereits responded)
            await interaction.followup.send(
                f"✅ Dein {ticket_type} Ticket wurde erstellt: {ticket_channel.mention}", 
                ephemeral=True
            )
            
            # Update counter AFTER everything else is done (with longer delay)
            asyncio.create_task(delayed_counter_update(guild, 3.0))
        except discord.errors.HTTPException as http_error:
            if http_error.status == 429:  # Rate limited
                print(f"⚠️ Rate limited during final operations - ticket still created successfully")
                await asyncio.sleep(2.0)  # Wait longer on rate limit
                try:
                    await interaction.followup.send(
                        f"✅ Dein {ticket_type} Ticket wurde erstellt: {ticket_channel.mention}", 
                        ephemeral=True
                    )
                except:
                    print(f"✅ Ticket {channel_name} created successfully (confirmation delayed due to rate limits)")
            else:
                print(f"⚠️ HTTP error in final ticket operations: {http_error}")
        except Exception as final_error:
            print(f"⚠️ Non-critical error in final ticket operations: {final_error}")
            # Still confirm ticket creation even if logging fails
            try:
                await interaction.followup.send(
                    f"✅ Dein {ticket_type} Ticket wurde erstellt: {ticket_channel.mention}", 
                    ephemeral=True
                )
            except:
                print(f"✅ Ticket {channel_name} created successfully (confirmation failed due to rate limits)")
        
        print(f"🎫 Neues Ticket erstellt: {channel_name} von {user} (Typ: {ticket_type})")
        
    except Exception as e:
        print(f"❌ Fehler beim Erstellen des Tickets: {e}")
        await interaction.followup.send(
            "❌ Fehler beim Erstellen des Tickets. Bitte kontaktiere einen Administrator.", 
            ephemeral=True
        )

# Review system
async def start_review_system(ticket_channel, user):
    embed = discord.Embed(
        title="⭐ Kundenbewertung",
        description=f"Hallo {user.mention}!\n\nDeine Bestellung wurde abgeschlossen. Wie zufrieden warst du mit unserem Service?\n\n**Bitte wähle eine Bewertung von 1-5 Sternen:**",
        color=0xffd700
    )
    
    review_view = View(timeout=None)
    
    # Create star rating buttons 1-5
    star_buttons = [
        ("1⭐", 1),
        ("2⭐", 2), 
        ("3⭐", 3),
        ("4⭐", 4),
        ("5⭐", 5)
    ]
    
    def create_rating_callback(rating_value):
        async def rating_callback(rating_interaction):
            if rating_interaction.user.id != user.id:
                await rating_interaction.response.send_message("❌ Nur der Kunde kann eine Bewertung abgeben.", ephemeral=True)
                return
            
            # Open review modal
            modal = ReviewModal(user, rating_value)
            await rating_interaction.response.send_modal(modal)
        return rating_callback
    
    for label, rating in star_buttons:
        button = Button(label=label, style=discord.ButtonStyle.secondary)
        button.callback = create_rating_callback(rating)
        review_view.add_item(button)
    
    await ticket_channel.send(embed=embed, view=review_view)
    print(f"⭐ Review-System gestartet für {user} in {ticket_channel.name}")

# Slash Command: /ticket_panel
@bot.tree.command(name="ticket_panel", description="Erstelle das Ticket-Panel (nur für Administratoren)")
async def ticket_panel_cmd(interaction: discord.Interaction):
    print(f"🎫 /ticket_panel command verwendet von {interaction.user}")
    
    # Nur Administratoren können das Panel erstellen
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung, das Ticket-Panel zu erstellen.", 
            ephemeral=True
        )
        return
    
    # Ticket-Panel Design
    embed = discord.Embed(
        title="🎫 TICKET SYSTEM",
        description="""
╔═══════════════════════════════════════╗
║              🌪️ HAZE VISUALS 🌪️              ║
║            ✨ Support Center ✨            ║
╚═══════════════════════════════════════╝

📞 **Brauchst du Hilfe?**
Klicke auf einen der Buttons unten, um ein Ticket zu erstellen:

🛒 **Bestellung** - Für Aufträge und Kaufanfragen
🛍️ **Shop** - Soundpacks, Templates & Discord Bots
🛠️ **Support** - Allgemeine Hilfe und Fragen  
🐛 **Bug Report** - Probleme melden
💡 **Vorschlag** - Ideen und Feedback
📋 **Bewerbung** - Team-Bewerbungen

⚡ **Hinweise:**
• Ein Ticket pro Person zur gleichen Zeit
• Unser Team antwortet so schnell wie möglich
• Verwende die richtige Kategorie für dein Anliegen
        """,
        color=0x7289da
    )
    embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757177441437.gif")
    embed.set_footer(text="Haze Visuals • Ticket System")
    
    # Ticket-Buttons
    view = View(timeout=None)
    
    ticket_types = [
        ("🛒 Bestellung", "Bestellung", discord.ButtonStyle.success),
        ("🛍️ Shop", "Shop", discord.ButtonStyle.blurple),
        ("🛠️ Support", "Support", discord.ButtonStyle.primary),
        ("🐛 Bug Report", "Bug Report", discord.ButtonStyle.danger),
        ("💡 Vorschlag", "Vorschlag", discord.ButtonStyle.secondary),
        ("📋 Bewerbung", "Bewerbung", discord.ButtonStyle.success)
    ]
    
    # Callbacks werden jetzt vom globalen Handler verwaltet
    
    for label, ticket_type, style in ticket_types:
        # Erstelle persistente Buttons mit custom_ids
        button = Button(
            label=label, 
            style=style, 
            custom_id=f"ticket_{ticket_type.lower().replace(' ', '_')}"
        )
        view.add_item(button)
    
    # Sende Banner als Datei mit
    banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757177441437.gif", 
                              filename="bannergif-ezgif.com-video-to-gif-converter_1757177441437.gif")
    
    await interaction.response.send_message(embed=embed, view=view, file=banner_file)
    print("✅ Ticket-Panel erfolgreich erstellt")

# Helper function to create button callback
def create_button_callback(kategorie_name):
    async def button_callback(interaction):
        print(f"📌 Button geklickt: {kategorie_name} von {interaction.user}")
        try:
            await interaction.response.send_message(f"**Preise für {kategorie_name}:**\n{preise[kategorie_name]}", ephemeral=True)
            print(f"✅ Preis-Info für {kategorie_name} erfolgreich gesendet an {interaction.user}")
        except Exception as e:
            print(f"❌ Fehler beim Senden der Preis-Info für {kategorie_name}: {e}")
            try:
                await interaction.response.send_message("❌ Fehler beim Laden der Preisinformationen.", ephemeral=True)
            except:
                pass
    return button_callback

# Slash Command: /terminerefresh
@bot.tree.command(name="terminerefresh", description="Lösche alle gebuchten Termine (nur für HV | Team)")
async def termine_refresh_cmd(interaction: discord.Interaction):
    print(f"📅 /terminerefresh command verwendet von {interaction.user}")
    
    # Check HV | Team role permission
    if not interaction.user.guild_permissions.administrator:
        hv_team_role = discord.utils.get(interaction.guild.roles, name="HV | Team")
        if not hv_team_role or hv_team_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung für diesen Befehl. Nur HV | Team kann Termine refreshen.", 
                ephemeral=True
            )
            return
    
    try:
        # Clear all appointments
        cleared_count = await clear_all_appointments()
        
        if cleared_count > 0:
            await interaction.response.send_message(
                f"✅ **Termine erfolgreich gelöscht!**\n\n📅 **{cleared_count} Termine** wurden freigegeben und der Kalender wurde aktualisiert.\n\n🔄 Alle Terminslots sind jetzt wieder verfügbar.", 
                ephemeral=True
            )
            print(f"✅ {cleared_count} Termine von {interaction.user} gelöscht")
        else:
            await interaction.response.send_message(
                "ℹ️ Es waren keine Termine zum Löschen vorhanden.\n\nDer Kalender ist bereits vollständig frei.", 
                ephemeral=True
            )
            print(f"ℹ️ Keine Termine zum Löschen gefunden (angefragt von {interaction.user})")
            
    except Exception as e:
        print(f"❌ Fehler in /terminerefresh command: {e}")
        await interaction.response.send_message(
            "❌ Ein Fehler ist beim Löschen der Termine aufgetreten. Bitte kontaktiere einen Administrator.", 
            ephemeral=True
        )

# Server Setup Modal Classes
class CustomCategoryModal(Modal):
    def __init__(self, guild_id):
        super().__init__(title="➕ Neue Ticket Kategorie erstellen")
        self.guild_id = guild_id
        
        self.category_name = TextInput(
            label="Kategorie Name",
            placeholder="z.B. VIP Support, Premium Orders...",
            required=True,
            max_length=50
        )
        
        self.category_color = TextInput(
            label="Button Farbe (Hex Code)",
            placeholder="z.B. #ff0000 für rot, #00ff00 für grün...",
            required=False,
            max_length=7,
            default="#7289da"
        )
        
        self.category_id = TextInput(
            label="Discord Kategorie ID (optional)",
            placeholder="ID der Discord-Kategorie für diese Tickets...",
            required=False,
            max_length=20
        )
        
        self.category_emoji = TextInput(
            label="Emoji (optional)",
            placeholder="z.B. 👑, ⭐, 💎...",
            required=False,
            max_length=10
        )
        
        self.add_item(self.category_name)
        self.add_item(self.category_color)
        self.add_item(self.category_id)
        self.add_item(self.category_emoji)
    
    async def on_submit(self, interaction: discord.Interaction):
        config = get_server_config(self.guild_id)
        
        # Validate hex color
        color_value = self.category_color.value or "#7289da"
        if not color_value.startswith("#") or len(color_value) != 7:
            await interaction.response.send_message(
                "❌ **Ungültige Farbe!**\n\nBitte verwende ein gültiges Hex-Format wie #ff0000", 
                ephemeral=True
            )
            return
        
        # Initialize custom_categories if not exists
        if "custom_categories" not in config:
            config["custom_categories"] = {}
        
        category_name = self.category_name.value
        emoji = self.category_emoji.value or "🎫"
        
        # Add to custom categories
        config["custom_categories"][category_name] = {
            "name": category_name,
            "color": color_value,
            "category_id": int(self.category_id.value) if self.category_id.value else None,
            "emoji": emoji
        }
        
        save_server_config(self.guild_id, config)
        
        await interaction.response.send_message(
            f"✅ **Kategorie '{category_name}' erstellt!**\n\n"
            f"{emoji} **Name:** {category_name}\n"
            f"🎨 **Farbe:** {color_value}\n"
            f"📁 **Kategorie ID:** {self.category_id.value or 'Nicht gesetzt'}\n\n"
            f"Die neue Kategorie wird beim nächsten Erstellen des Ticket-Panels angezeigt.",
            ephemeral=True
        )

class PaymentSettingsModal(Modal):
    def __init__(self, guild_id):
        super().__init__(title="💰 Zahlungseinstellungen")
        self.guild_id = guild_id
        
        config = get_server_config(guild_id)
        payment_settings = config.get("payment_settings", {})
        
        self.paypal_email = TextInput(
            label="PayPal Email Adresse",
            placeholder="z.B. business@example.com",
            required=False,
            max_length=100,
            default=payment_settings.get("paypal_email", "hazeevisuals@gmail.com")
        )
        
        self.bank_name = TextInput(
            label="Bank Name",
            placeholder="z.B. Deutsche Bank, Sparkasse...",
            required=False,
            max_length=100,
            default=payment_settings.get("bank_name", "")
        )
        
        self.iban = TextInput(
            label="IBAN",
            placeholder="DE89 3704 0044 0532 0130 00",
            required=False,
            max_length=34,
            default=payment_settings.get("iban", "")
        )
        
        self.account_holder = TextInput(
            label="Kontoinhaber",
            placeholder="Name des Kontoinhabers",
            required=False,
            max_length=100,
            default=payment_settings.get("account_holder", "")
        )
        
        self.add_item(self.paypal_email)
        self.add_item(self.bank_name)
        self.add_item(self.iban)
        self.add_item(self.account_holder)
    
    async def on_submit(self, interaction: discord.Interaction):
        config = get_server_config(self.guild_id)
        
        # Initialize payment_settings if not exists
        if "payment_settings" not in config:
            config["payment_settings"] = {}
        
        # Update payment settings
        config["payment_settings"].update({
            "paypal_email": self.paypal_email.value,
            "bank_name": self.bank_name.value,
            "iban": self.iban.value,
            "account_holder": self.account_holder.value
        })
        
        save_server_config(self.guild_id, config)
        
        await interaction.response.send_message(
            "✅ **Zahlungseinstellungen gespeichert!**\n\n"
            f"💳 **PayPal:** {self.paypal_email.value or 'Nicht gesetzt'}\n"
            f"🏦 **Bank:** {self.bank_name.value or 'Nicht gesetzt'}\n"
            f"💰 **IBAN:** {self.iban.value or 'Nicht gesetzt'}\n"
            f"👤 **Kontoinhaber:** {self.account_holder.value or 'Nicht gesetzt'}",
            ephemeral=True
        )

class LanguageSettingsModal(Modal):
    def __init__(self, guild_id):
        super().__init__(title="🌍 Sprache ändern")
        self.guild_id = guild_id
        
        config = get_server_config(guild_id)
        current_language = config.get("language", "german")
        
        self.language_selection = TextInput(
            label="Sprache auswählen",
            placeholder="german, english, spanish, italian, french",
            required=True,
            max_length=20,
            default=current_language
        )
        
        self.add_item(self.language_selection)
    
    async def on_submit(self, interaction: discord.Interaction):
        valid_languages = ["german", "english", "spanish", "italian", "french"]
        selected_language = self.language_selection.value.lower().strip()
        
        if selected_language not in valid_languages:
            await interaction.response.send_message(
                f"❌ **Ungültige Sprache!**\n\n"
                f"Verfügbare Sprachen: {', '.join(valid_languages)}",
                ephemeral=True
            )
            return
        
        config = get_server_config(self.guild_id)
        config["language"] = selected_language
        save_server_config(self.guild_id, config)
        
        language_names = {
            "german": "🇩🇪 Deutsch",
            "english": "🇺🇸 English", 
            "spanish": "🇪🇸 Español",
            "italian": "🇮🇹 Italiano",
            "french": "🇫🇷 Français"
        }
        
        await interaction.response.send_message(
            f"✅ **Sprache geändert!**\n\n"
            f"Neue Sprache: {language_names[selected_language]}\n\n"
            f"⚠️ **Hinweis:** Das Übersetzungssystem ist noch in Entwicklung. "
            f"Derzeit sind die meisten Texte noch auf Deutsch.",
            ephemeral=True
        )

class TicketCategoriesModal(Modal):
    def __init__(self, guild_id):
        super().__init__(title="🏷️ Ticket Kategorien einrichten")
        self.guild_id = guild_id
        
        self.bestellung_cat = TextInput(
            label="Bestellung Kategorie ID",
            placeholder="ID der Kategorie für Bestellungen...",
            required=False,
            max_length=20
        )
        
        self.support_cat = TextInput(
            label="Support Kategorie ID", 
            placeholder="ID der Kategorie für Support...",
            required=False,
            max_length=20
        )
        
        self.paid_cat = TextInput(
            label="Paid Kategorie ID",
            placeholder="ID der Kategorie für bezahlte Tickets...",
            required=False,
            max_length=20
        )
        
        self.review_cat = TextInput(
            label="Review Kategorie ID",
            placeholder="ID der Kategorie für Reviews...",
            required=False,
            max_length=20
        )
        
        self.add_item(self.bestellung_cat)
        self.add_item(self.support_cat)
        self.add_item(self.paid_cat)
        self.add_item(self.review_cat)
    
    async def on_submit(self, interaction: discord.Interaction):
        config = get_server_config(self.guild_id)
        
        # Update ticket categories
        if self.bestellung_cat.value:
            config.setdefault("categories", {})["open"] = int(self.bestellung_cat.value)
        if self.support_cat.value:
            config.setdefault("categories", {})["claimed"] = int(self.support_cat.value)
        if self.paid_cat.value:
            config.setdefault("categories", {})["paid"] = int(self.paid_cat.value)
        if self.review_cat.value:
            config.setdefault("categories", {})["finished"] = int(self.review_cat.value)
        
        save_server_config(self.guild_id, config)
        
        await interaction.response.send_message(
            "✅ **Ticket Kategorien konfiguriert!**\n\nDie Kategorie-IDs wurden erfolgreich gespeichert.", 
            ephemeral=True
        )

class CustomCategoryModal(Modal):
    def __init__(self, guild_id):
        super().__init__(title="➕ Neue Ticket Kategorie erstellen")
        self.guild_id = guild_id
        
        self.category_name = TextInput(
            label="Kategorie Name",
            placeholder="z.B. VIP Support, Premium Service...",
            required=True,
            max_length=50
        )
        
        self.category_id = TextInput(
            label="Discord Kategorie ID",
            placeholder="ID der Discord-Kategorie für diese Tickets...",
            required=True,
            max_length=20
        )
        
        self.button_color = TextInput(
            label="Button Farbe (Hex Code)",
            placeholder="z.B. #FF5733, #00FF00, #3498DB...",
            required=True,
            max_length=7,
            default="#7289da"
        )
        
        self.button_emoji = TextInput(
            label="Button Emoji",
            placeholder="z.B. ⭐, 💎, 🎯, 🔥...",
            required=False,
            max_length=2
        )
        
        self.add_item(self.category_name)
        self.add_item(self.category_id)
        self.add_item(self.button_color)
        self.add_item(self.button_emoji)
    
    async def on_submit(self, interaction: discord.Interaction):
        config = get_server_config(self.guild_id)
        
        # Validate hex color
        hex_color = self.button_color.value
        if not hex_color.startswith('#'):
            hex_color = '#' + hex_color
        
        try:
            # Test if it's a valid hex color
            int(hex_color[1:], 16)
        except ValueError:
            await interaction.response.send_message(
                "❌ **Ungültige Farbe!**\n\nBitte verwende einen gültigen Hex-Code (z.B. #FF5733).", 
                ephemeral=True
            )
            return
        
        # Validate category ID
        try:
            category_id = int(self.category_id.value)
            # Check if category exists
            category = interaction.guild.get_channel(category_id)
            if not category or not isinstance(category, discord.CategoryChannel):
                await interaction.response.send_message(
                    "❌ **Kategorie nicht gefunden!**\n\nBitte überprüfe die Kategorie-ID.", 
                    ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "❌ **Ungültige Kategorie-ID!**\n\nBitte verwende eine gültige Zahl.", 
                ephemeral=True
            )
            return
        
        # Create custom categories section if it doesn't exist
        if "custom_categories" not in config:
            config["custom_categories"] = {}
        
        # Add the new custom category
        config["custom_categories"][self.category_name.value] = {
            "category_id": category_id,
            "color": hex_color,
            "emoji": self.button_emoji.value or "🎫"
        }
        
        save_server_config(self.guild_id, config)
        
        await interaction.response.send_message(
            f"✅ **Neue Ticket Kategorie erstellt!**\n\n"
            f"**Name:** {self.category_name.value}\n"
            f"**Kategorie:** {category.name}\n"
            f"**Farbe:** {hex_color}\n"
            f"**Emoji:** {self.button_emoji.value or '🎫'}\n\n"
            f"Die neue Kategorie erscheint beim nächsten `/ticket_panel` Befehl!", 
            ephemeral=True
        )

class ChannelsModal(Modal):
    def __init__(self, guild_id):
        super().__init__(title="📢 Kanäle einrichten")
        self.guild_id = guild_id
        
        self.welcome_channel = TextInput(
            label="Welcome Kanal ID",
            placeholder="ID des Kanals für Willkommensnachrichten...",
            required=False,
            max_length=20
        )
        
        self.leave_channel = TextInput(
            label="Leave Kanal ID",
            placeholder="ID des Kanals für Verlassen-Nachrichten...",
            required=False,
            max_length=20
        )
        
        self.calendar_channel = TextInput(
            label="Kalender Kanal ID",
            placeholder="ID des Kanals für den Terminkalender...",
            required=False,
            max_length=20
        )
        
        self.review_channel = TextInput(
            label="Review Kanal ID",
            placeholder="ID des Kanals für Kundenbewertungen...",
            required=False,
            max_length=20
        )
        
        self.add_item(self.welcome_channel)
        self.add_item(self.leave_channel)
        self.add_item(self.calendar_channel)
        self.add_item(self.review_channel)
    
    async def on_submit(self, interaction: discord.Interaction):
        config = get_server_config(self.guild_id)
        
        # Update channels
        if self.welcome_channel.value:
            config["channels"]["welcome_channel"] = int(self.welcome_channel.value)
        if self.leave_channel.value:
            config["channels"]["leave_channel"] = int(self.leave_channel.value)
        if self.calendar_channel.value:
            config["channels"]["calendar_channel"] = int(self.calendar_channel.value)
        if self.review_channel.value:
            config["channels"]["review_channel"] = int(self.review_channel.value)
        
        save_server_config(self.guild_id, config)
        
        await interaction.response.send_message(
            "✅ **Kanäle konfiguriert!**\n\nDie Kanal-IDs wurden erfolgreich gespeichert.", 
            ephemeral=True
        )

class EditMainView(View):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
    
    @discord.ui.button(label="💰 Zahlungseinstellungen", style=discord.ButtonStyle.primary)
    async def payment_settings(self, interaction: discord.Interaction, button: Button):
        modal = PaymentSettingsModal(self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🌍 Sprache ändern", style=discord.ButtonStyle.primary)
    async def language_settings(self, interaction: discord.Interaction, button: Button):
        modal = LanguageSettingsModal(self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="💲 Preise bearbeiten", style=discord.ButtonStyle.secondary)
    async def edit_prices(self, interaction: discord.Interaction, button: Button):
        # Show current prices for editing
        await interaction.response.send_message(
            "💲 **Preise bearbeiten**\n\nDiese Funktion ist noch in Entwicklung. "
            "Verwende vorerst die JSON-Datei zum direkten Bearbeiten der Preise.",
            ephemeral=True
        )

class SetupView(View):
    def __init__(self, guild_id):
        super().__init__(timeout=300)
        self.guild_id = guild_id
    
    @discord.ui.button(label="🏷️ Ticket Kategorien", style=discord.ButtonStyle.primary)
    async def setup_categories(self, interaction: discord.Interaction, button: Button):
        modal = TicketCategoriesModal(self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📢 Kanäle", style=discord.ButtonStyle.primary)
    async def setup_channels(self, interaction: discord.Interaction, button: Button):
        modal = ChannelsModal(self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⚙️ Features", style=discord.ButtonStyle.secondary)
    async def setup_features(self, interaction: discord.Interaction, button: Button):
        config = get_server_config(self.guild_id)
        
        # Toggle features
        features = config["features"]
        features_text = "🔧 **Aktuelle Feature-Einstellungen:**\n\n"
        
        for feature, enabled in features.items():
            status = "✅" if enabled else "❌"
            feature_name = feature.replace("_", " ").title()
            features_text += f"{status} {feature_name}\n"
        
        features_text += "\n💡 **Hinweis:** Features können einzeln in der Konfigurationsdatei angepasst werden."
        
        await interaction.response.send_message(features_text, ephemeral=True)
    
    @discord.ui.button(label="➕ Neue Ticket Kategorie", style=discord.ButtonStyle.secondary)
    async def create_custom_category(self, interaction: discord.Interaction, button: Button):
        modal = CustomCategoryModal(self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📋 Aktuelle Config", style=discord.ButtonStyle.success)
    async def view_config(self, interaction: discord.Interaction, button: Button):
        config = get_server_config(self.guild_id)
        
        config_text = "⚙️ **Server Konfiguration:**\n\n"
        
        # Ticket Categories
        config_text += "🏷️ **Ticket Kategorien:**\n"
        categories = config.get("categories", {})
        category_names = {"open": "Offene Tickets", "claimed": "Bearbeitet", "paid": "Bezahlt", "finished": "Fertig"}
        for cat_key, cat_name in category_names.items():
            cat_id = categories.get(cat_key)
            status = f"<#{cat_id}>" if cat_id else "❌ Nicht konfiguriert"
            config_text += f"• {cat_name}: {status}\n"
        
        # Channels
        config_text += "\n📢 **Kanäle:**\n"
        for channel_name, channel_id in config["channels"].items():
            status = f"<#{channel_id}>" if channel_id else "❌ Nicht konfiguriert"
            channel_display = channel_name.replace("_", " ").title()
            config_text += f"• {channel_display}: {status}\n"
        
        # Features
        config_text += "\n⚙️ **Features:**\n"
        for feature, enabled in config["features"].items():
            status = "✅" if enabled else "❌"
            feature_name = feature.replace("_", " ").title()
            config_text += f"• {feature_name}: {status}\n"
        
        await interaction.response.send_message(config_text, ephemeral=True)

# Slash Command: /setup
@bot.tree.command(name="setup", description="Bot Setup für neue Server (nur für Administratoren)")
async def setup_cmd(interaction: discord.Interaction):
    print(f"⚙️ /setup command verwendet von {interaction.user} in {interaction.guild.name}")
    
    # Only administrators can use setup
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung für diesen Befehl. Nur Server-Administratoren können das Bot-Setup verwenden.", 
            ephemeral=True
        )
        return
    
    guild_id = interaction.guild.id
    
    embed = discord.Embed(
        title="🤖 Haze Visuals Bot Setup",
        description=f"""
Willkommen zum Bot-Setup für **{interaction.guild.name}**!

🏷️ **Ticket Kategorien** - Konfiguriere Discord-Kategorien für Tickets
📢 **Kanäle** - Setze spezielle Kanäle für Features ein
⚙️ **Features** - Zeige aktuelle Feature-Einstellungen
📋 **Aktuelle Config** - Zeige die komplette Server-Konfiguration

**Hinweise:**
• Alle Einstellungen sind pro Server gespeichert
• Du benötigst die Kanal-/Kategorie-IDs für die Konfiguration
• Features können nach dem Setup weiter angepasst werden
        """,
        color=0x00ff00
    )
    
    embed.set_footer(text="Haze Visuals • Server Setup")
    
    view = SetupView(guild_id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Persistente Preise View Klasse
class PersistentPricesView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.categories = []
    
    def set_categories(self, categories):
        self.categories = categories
        self.clear_items()
        
        # Erstelle persistente Buttons für jede Kategorie
        for i, kategorie in enumerate(categories):
            button = Button(
                label=kategorie,
                style=discord.ButtonStyle.primary,
                custom_id=f"prices_{kategorie.lower().replace(' ', '_')}_{i}"
            )
            self.add_item(button)
    
    # Note: interaction_check wird vom globalen Handler verwaltet

# Event Handler für persistente Buttons
@bot.event
async def on_interaction(interaction):
    """Globaler Handler für persistente Button-Interaktionen"""
    if interaction.type != discord.InteractionType.component:
        return
    
    custom_id = interaction.data.get("custom_id", "")
    
    # Handle Preise Buttons
    if custom_id.startswith("prices_"):
        parts = custom_id.split("_")
        if len(parts) >= 3:
            # Rekonstruiere Kategorie-Namen
            kategorie_parts = parts[1:-1]  # Alles außer "prices" und Index
            
            # Finde passende Kategorie in aktuellen Preisen
            preise = load_prices()
            for k in preise.keys():
                if k.lower().replace(" ", "_") == "_".join(kategorie_parts):
                    await show_category_prices(interaction, k)
                    return
        
        await interaction.response.send_message("❌ Kategorie nicht gefunden.", ephemeral=True)
        return
    
    # Handle Ticket Buttons
    elif custom_id.startswith("ticket_"):
        ticket_types = {
            "ticket_bestellung": "Bestellung",
            "ticket_shop": "Shop",
            "ticket_support": "Support", 
            "ticket_bug_report": "Bug Report",
            "ticket_vorschlag": "Vorschlag",
            "ticket_bewerbung": "Bewerbung"
        }
        
        if custom_id in ticket_types:
            ticket_type = ticket_types[custom_id]
            if ticket_type == "Shop":
                await create_shop_ticket(interaction)
            else:
                await create_ticket(interaction, ticket_type)
            return
    
    # Handle Admin Buttons
    elif custom_id.startswith("admin_"):
        admin_functions = {
            "admin_branding": show_branding_config,
            "admin_roles": show_roles_config,
            "admin_pricing": show_pricing_config,
            "admin_discount": show_discount_config,
            "admin_payment": show_payment_config,
            "admin_review": create_review_channel,
            "admin_messages": show_messages_config,
            "admin_quick_setup": show_quick_setup,
            "admin_statistics": show_bot_statistics
        }
        
        if custom_id in admin_functions:
            await admin_functions[custom_id](interaction)
            return
    
    # Handle Shop Buttons  
    elif custom_id.startswith("shop_"):
        # Implementierung für Shop-spezifische Buttons wenn benötigt
        await interaction.response.send_message("Shop-Button erkannt!", ephemeral=True)
        return

@bot.tree.command(name="preise", description="Zeigt die Preisliste an")
async def preise_cmd(interaction: discord.Interaction):
    print(f"📌 /preise command verwendet von {interaction.user}")
    try:
        # Persistente View (funktioniert nach Bot-Neustart)
        view = PersistentPricesView()

        # Setze die aktuellen Kategorien für die View
        view.set_categories(list(preise.keys()))

        # Banner für die Preisliste
        banner = """
╔═══════════════════════════════════════╗
║              🌪️ HAZE VISUALS 🌪️              ║
║          ✨ Premium Custom Designs ✨          ║
╚═══════════════════════════════════════╝

📋 **Unsere Preisliste**
🎨 Hochwertige Custom-Designs für dich!
💫 Klicke unten auf eine Kategorie:
        """
        
        await interaction.response.send_message(banner, view=view)
        print("✅ Preise message erfolgreich gesendet")
    except Exception as e:
        print(f"❌ Fehler in /preise command: {e}")
        try:
            await interaction.response.send_message("❌ Ein Fehler ist aufgetreten.", ephemeral=True)
        except:
            pass

# ========================================
# ADMIN CONFIGURATION SYSTEM
# ========================================

async def show_admin_config(interaction):
    """Show admin configuration panel (for button callbacks)"""
    await admin_config_command(interaction)

@bot.tree.command(name="admin", description="Umfassendes Admin-Konfigurationspanel für Server-Anpassungen")
async def admin_config_command(interaction: discord.Interaction):
    """Main admin configuration panel for complete bot customization"""
    
    # Check admin permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Du benötigst Administrator-Rechte für diesen Befehl.", 
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="⚙️ Bot Konfiguration",
        description="**Willkommen im Admin-Panel!**\n\nHier kannst du alle Aspekte des Bots für deinen Server anpassen. Wähle einen Bereich zur Konfiguration:",
        color=0x3498db
    )
    
    embed.add_field(
        name="🎨 Server Branding",
        value="• Bot-Name und Farben\n• Logo und Banner\n• Willkommensnachrichten",
        inline=True
    )
    
    embed.add_field(
        name="👥 Rollen & Kanäle",
        value="• Staff-Rollen konfigurieren\n• Ticket-Kategorien\n• Berechtigungen verwalten",
        inline=True
    )
    
    embed.add_field(
        name="💰 Preise & Produkte",
        value="• Produktkatalog bearbeiten\n• Preise anpassen\n• Neue Services hinzufügen",
        inline=True
    )
    
    embed.add_field(
        name="🎟️ Discount Codes",
        value="• Rabattcodes verwalten\n• Aktionen erstellen\n• Gültigkeitsdauer",
        inline=True
    )
    
    embed.add_field(
        name="💳 Zahlungsmethoden",
        value="• PayPal konfigurieren\n• Bank-Details\n• Weitere Optionen",
        inline=True
    )
    
    embed.add_field(
        name="⭐ Review System",
        value="• Review-Channel erstellen\n• Kundenbewertungen verwalten\n• Feedback-System",
        inline=True
    )
    
    
    embed.add_field(
        name="📝 Texte & Nachrichten",
        value="• Bot-Nachrichten anpassen\n• Sprache ändern\n• Custom Embeds",
        inline=True
    )
    
    embed.set_footer(text="Wähle einen Bereich zur Konfiguration • Nur für Administratoren")
    
    # Persistente Configuration menu
    config_view = View(timeout=None)
    
    # Persistente Admin-Buttons mit custom_ids
    branding_button = Button(label="🎨 Branding", style=discord.ButtonStyle.primary, row=0, custom_id="admin_branding")
    roles_button = Button(label="👥 Rollen & Kanäle", style=discord.ButtonStyle.primary, row=0, custom_id="admin_roles")
    pricing_button = Button(label="💰 Preise", style=discord.ButtonStyle.primary, row=0, custom_id="admin_pricing")
    discount_button = Button(label="🎟️ Discounts", style=discord.ButtonStyle.primary, row=1, custom_id="admin_discount")
    payment_button = Button(label="💳 Zahlungen", style=discord.ButtonStyle.primary, row=1, custom_id="admin_payment")
    review_button = Button(label="⭐ Review Channel", style=discord.ButtonStyle.success, row=1, custom_id="admin_review")
    messages_button = Button(label="📝 Texte", style=discord.ButtonStyle.primary, row=1, custom_id="admin_messages")
    quick_setup_button = Button(label="⚡ Schnell-Setup", style=discord.ButtonStyle.success, row=2, custom_id="admin_quick_setup")
    stats_button = Button(label="📊 Statistiken", style=discord.ButtonStyle.secondary, row=2, custom_id="admin_statistics")
    
    config_view.add_item(branding_button)
    config_view.add_item(roles_button)
    config_view.add_item(pricing_button)
    config_view.add_item(discount_button)
    config_view.add_item(payment_button)
    config_view.add_item(review_button)
    config_view.add_item(messages_button)
    config_view.add_item(quick_setup_button)
    config_view.add_item(stats_button)
    
    await interaction.response.send_message(embed=embed, view=config_view, ephemeral=True)

# ========================================
# CONFIGURATION PANEL FUNCTIONS
# ========================================

async def show_branding_config(interaction):
    """Server branding and appearance configuration"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    server_config = get_server_config(interaction.guild.id)
    
    embed = discord.Embed(
        title="🎨 Server Branding Konfiguration",
        description="Passe das Aussehen und Branding des Bots für deinen Server an:",
        color=0xe91e63
    )
    
    current_name = server_config.get("branding", {}).get("bot_name", "Haze Visuals")
    current_color = server_config.get("branding", {}).get("primary_color", "#7289da")
    
    embed.add_field(
        name="🤖 Aktueller Bot-Name",
        value=f"`{current_name}`",
        inline=True
    )
    
    embed.add_field(
        name="🎨 Aktuelle Hauptfarbe",
        value=f"`{current_color}`",
        inline=True
    )
    
    embed.add_field(
        name="📋 Verfügbare Optionen",
        value="• Bot-Name ändern\n• Hauptfarbe anpassen\n• Footer-Text bearbeiten\n• Willkommensnachricht",
        inline=False
    )
    
    branding_view = View(timeout=300)
    
    # Bot name button
    name_button = Button(label="🤖 Bot-Name ändern", style=discord.ButtonStyle.primary)
    name_button.callback = lambda i: show_bot_name_modal(i)
    
    # Color button
    color_button = Button(label="🎨 Farbe ändern", style=discord.ButtonStyle.primary)
    color_button.callback = lambda i: show_color_modal(i)
    
    # Footer button
    footer_button = Button(label="📝 Footer bearbeiten", style=discord.ButtonStyle.secondary)
    footer_button.callback = lambda i: show_footer_modal(i)
    
    # Back button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.danger)
    back_button.callback = lambda i: show_admin_config(i)
    
    # Banner button
    banner_button = Button(label="🖼️ Banner", style=discord.ButtonStyle.secondary)
    banner_button.callback = lambda i: show_banner_config(i)
    
    branding_view.add_item(name_button)
    branding_view.add_item(color_button)
    branding_view.add_item(footer_button)
    branding_view.add_item(banner_button)
    branding_view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=branding_view, ephemeral=True)

async def show_roles_config(interaction):
    """Roles and channels configuration"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    server_config = get_server_config(interaction.guild.id)
    
    embed = discord.Embed(
        title="👥 Rollen & Kanäle Konfiguration",
        description="Konfiguriere Rollen und Kanäle für dein Server-Setup:",
        color=0x9b59b6
    )
    
    admin_role = server_config.get("roles", {}).get("admin_role", "Admin")
    staff_role = server_config.get("roles", {}).get("staff_role", "HV | Team")
    customer_role = server_config.get("roles", {}).get("customer_role", "Customer")
    
    embed.add_field(
        name="👑 Admin-Rolle",
        value=f"`{admin_role}`",
        inline=True
    )
    
    embed.add_field(
        name="🛠️ Staff-Rolle",
        value=f"`{staff_role}`",
        inline=True
    )
    
    embed.add_field(
        name="👤 Kunden-Rolle",
        value=f"`{customer_role}`",
        inline=True
    )
    
    embed.add_field(
        name="📋 Ticket-Kategorien",
        value="• Bestellung\n• Support\n• Review\n• Paid",
        inline=False
    )
    
    roles_view = View(timeout=300)
    
    # Admin role button
    admin_button = Button(label="👑 Admin-Rolle", style=discord.ButtonStyle.primary)
    admin_button.callback = lambda i: show_admin_role_modal(i)
    
    # Staff role button
    staff_button = Button(label="🛠️ Staff-Rolle", style=discord.ButtonStyle.primary)
    staff_button.callback = lambda i: show_staff_role_modal(i)
    
    # Customer role button
    customer_button = Button(label="👤 Kunden-Rolle", style=discord.ButtonStyle.primary)
    customer_button.callback = lambda i: show_customer_role_modal(i)
    
    # Categories button
    categories_button = Button(label="📁 Kategorien", style=discord.ButtonStyle.secondary)
    categories_button.callback = lambda i: show_categories_config(i)
    
    # Back button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.danger)
    back_button.callback = lambda i: show_admin_config(i)
    
    roles_view.add_item(admin_button)
    roles_view.add_item(staff_button)
    roles_view.add_item(customer_button)
    roles_view.add_item(categories_button)
    roles_view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=roles_view, ephemeral=True)

async def show_pricing_config(interaction):
    """Pricing and products configuration"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="💰 Preise & Produkte Konfiguration",
        description="Verwalte deine Produkte und Preise:",
        color=0xf39c12
    )
    
    embed.add_field(
        name="🛍️ Aktuelle Produkte",
        value="• Custom Paket - 20€\n• Fertiges Paket - 10€\n• Custom einzeln - 5€\n• Custom Weste - 10€",
        inline=True
    )
    
    embed.add_field(
        name="⚙️ Verfügbare Aktionen",
        value="• Preise bearbeiten\n• Neue Produkte hinzufügen\n• Produkte entfernen\n• Kategorien verwalten\n• Shop-Kategorien mit Farben",
        inline=True
    )
    
    pricing_view = View(timeout=300)
    
    # Edit prices button
    edit_prices_button = Button(label="✏️ Preise bearbeiten", style=discord.ButtonStyle.primary)
    edit_prices_button.callback = lambda i: show_edit_prices_modal(i)
    
    # Add product button
    add_product_button = Button(label="➕ Produkt hinzufügen", style=discord.ButtonStyle.success)
    add_product_button.callback = lambda i: show_add_product_modal(i)
    
    # Categories button
    manage_categories_button = Button(label="📁 Kategorien", style=discord.ButtonStyle.secondary)
    manage_categories_button.callback = lambda i: show_pricing_categories_modal(i)
    
    # Shop Categories button
    shop_categories_button = Button(label="🛍️ Shop-Kategorien", style=discord.ButtonStyle.blurple)
    shop_categories_button.callback = lambda i: show_shop_categories_config(i)
    
    # Back button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.danger)
    back_button.callback = lambda i: show_admin_config(i)
    
    pricing_view.add_item(edit_prices_button)
    pricing_view.add_item(add_product_button)
    pricing_view.add_item(manage_categories_button)
    pricing_view.add_item(shop_categories_button)
    pricing_view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=pricing_view, ephemeral=True)

async def show_discount_config(interaction):
    """Discount codes configuration"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    # Load current discount codes
    discount_codes = load_discount_codes()
    
    embed = discord.Embed(
        title="🎟️ Discount Codes Konfiguration",
        description="Verwalte deine Rabattcodes:",
        color=0x8e44ad
    )
    
    if discount_codes:
        codes_text = ""
        for code, data in discount_codes.items():
            if isinstance(data, dict):
                # New format
                discount_type = data.get("type", "percentage")
                value = data.get("value", 0)
                max_uses = data.get("max_uses", -1)
                current_uses = data.get("current_uses", 0)
                
                if discount_type == "percentage":
                    discount_info = f"{int(value * 100)}%"
                else:
                    discount_info = f"{value}€"
                
                if max_uses == -1:
                    usage_info = "∞"
                else:
                    usage_info = f"{current_uses}/{max_uses}"
                
                status = "🟢" if (max_uses == -1 or current_uses < max_uses) else "🔴"
                codes_text += f"{status} **{code}** - {discount_info} ({usage_info})\n"
            else:
                # Old format fallback
                percentage = int(data * 100)
                codes_text += f"🟢 **{code}** - {percentage}% (∞)\n"
    else:
        codes_text = "Keine Codes vorhanden"
    
    embed.add_field(
        name="🎯 Aktuelle Codes",
        value=codes_text[:1024],  # Discord limit
        inline=False
    )
    
    # Summary statistics
    total_codes = len(discount_codes)
    active_codes = len([code for code, data in discount_codes.items() if data.get("max_uses", -1) == -1 or data.get("current_uses", 0) < data.get("max_uses", 0)])
    single_use_codes = len([code for code, data in discount_codes.items() if data.get("max_uses", 1) == 1])
    
    embed.add_field(
        name="📈 Statistiken",
        value=f"📊 **Gesamt:** {total_codes}\n🟢 **Aktiv:** {active_codes}\n🎫 **Einmalig:** {single_use_codes}",
        inline=True
    )
    
    discount_view = View(timeout=300)
    
    # Add code button
    add_code_button = Button(label="➕ Code hinzufügen", style=discord.ButtonStyle.success)
    add_code_button.callback = lambda i: show_add_enhanced_discount_modal(i)
    
    # Single use code button
    single_use_button = Button(label="🎫 Einmaliger Code", style=discord.ButtonStyle.blurple)
    single_use_button.callback = lambda i: show_single_use_discount_modal(i)
    
    # Auto-delete code button
    auto_delete_button = Button(label="🗑️ Auto-Lösch-Code", style=discord.ButtonStyle.success)
    auto_delete_button.callback = lambda i: show_auto_delete_discount_modal(i)
    
    # Remove code button
    remove_code_button = Button(label="🗑️ Code entfernen", style=discord.ButtonStyle.danger)
    remove_code_button.callback = lambda i: show_remove_discount_modal(i)
    
    # Reset usage button
    reset_usage_button = Button(label="🔄 Nutzung zurücksetzen", style=discord.ButtonStyle.secondary)
    reset_usage_button.callback = lambda i: show_reset_discount_usage_modal(i)
    
    # Back button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_admin_config(i)
    
    discount_view.add_item(add_code_button)
    discount_view.add_item(single_use_button)
    discount_view.add_item(auto_delete_button)
    discount_view.add_item(remove_code_button)
    discount_view.add_item(reset_usage_button)
    discount_view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=discount_view, ephemeral=True)

async def show_payment_config(interaction):
    """Payment methods configuration"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    server_config = get_server_config(interaction.guild.id)
    
    embed = discord.Embed(
        title="💳 Zahlungsmethoden Konfiguration",
        description="Konfiguriere deine Zahlungsoptionen:",
        color=0x27ae60
    )
    
    paypal_email = server_config.get("payment", {}).get("paypal_email", "hazeevisuals@gmail.com")
    bank_info = server_config.get("payment", {}).get("bank_info", "Nicht konfiguriert")
    
    # Status aller Zahlungsmethoden
    paypal_enabled = server_config.get("payment", {}).get("paypal_enabled", True)
    bank_enabled = server_config.get("payment", {}).get("bank_enabled", True)
    paysafe_enabled = server_config.get("payment", {}).get("paysafe_enabled", True)
    
    embed.add_field(
        name="💙 PayPal",
        value=f"Email: `{paypal_email}`\nStatus: {'✅ Aktiviert' if paypal_enabled else '❌ Deaktiviert'}",
        inline=True
    )
    
    embed.add_field(
        name="🏦 Bank Transfer",
        value=f"IBAN: `{server_config.get('payment', {}).get('iban', 'Nicht konfiguriert')}`\nStatus: {'✅ Aktiviert' if bank_enabled else '❌ Deaktiviert'}",
        inline=True
    )
    
    embed.add_field(
        name="💳 Paysafecard",
        value=f"Status: {'✅ Aktiviert' if paysafe_enabled else '❌ Deaktiviert'}",
        inline=True
    )
    
    payment_view = View(timeout=300)
    
    # PayPal button
    paypal_button = Button(label="💙 PayPal konfigurieren", style=discord.ButtonStyle.primary)
    paypal_button.callback = lambda i: show_paypal_modal(i)
    
    # Bank button
    bank_button = Button(label="🏦 Bank konfigurieren", style=discord.ButtonStyle.primary)
    bank_button.callback = lambda i: show_bank_modal(i)
    
    # Payment Toggle button
    toggle_button = Button(label="⚡ Zahlungen verwalten", style=discord.ButtonStyle.secondary)
    toggle_button.callback = lambda i: show_payment_toggles(i)
    
    # Additional methods button
    additional_button = Button(label="➕ Weitere Methoden", style=discord.ButtonStyle.secondary)
    additional_button.callback = lambda i: show_additional_payment_modal(i)
    
    # Back button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.danger)
    back_button.callback = lambda i: show_admin_config(i)
    
    payment_view.add_item(paypal_button)
    payment_view.add_item(bank_button)
    payment_view.add_item(toggle_button)
    payment_view.add_item(additional_button)
    payment_view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=payment_view, ephemeral=True)

async def show_messages_config(interaction):
    """Messages and text configuration"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📝 Texte & Nachrichten Konfiguration",
        description="Passe Bot-Nachrichten und Texte an:",
        color=0x34495e
    )
    
    embed.add_field(
        name="✉️ Anpassbare Bereiche",
        value="• Willkommensnachrichten\n• Ticket-Nachrichten\n• Zahlungsbestätigungen\n• Fehlermeldungen",
        inline=True
    )
    
    embed.add_field(
        name="🌐 Sprache",
        value="• Deutsch (Aktuell)\n• English\n• Custom Text",
        inline=True
    )
    
    messages_view = View(timeout=300)
    
    # Welcome messages
    welcome_button = Button(label="👋 Willkommensnachrichten", style=discord.ButtonStyle.primary)
    welcome_button.callback = lambda i: show_welcome_messages_modal(i)
    
    # Ticket messages
    ticket_button = Button(label="🎫 Ticket-Nachrichten", style=discord.ButtonStyle.primary)
    ticket_button.callback = lambda i: show_ticket_messages_modal(i)
    
    # Error messages
    error_button = Button(label="⚠️ Fehlermeldungen", style=discord.ButtonStyle.secondary)
    error_button.callback = lambda i: show_error_messages_modal(i)
    
    # Language button
    language_button = Button(label="🌐 Sprache", style=discord.ButtonStyle.secondary)
    language_button.callback = lambda i: show_language_modal(i)
    
    # Back button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.danger)
    back_button.callback = lambda i: show_admin_config(i)
    
    messages_view.add_item(welcome_button)
    messages_view.add_item(ticket_button)
    messages_view.add_item(error_button)
    messages_view.add_item(language_button)
    messages_view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=messages_view, ephemeral=True)

async def show_quick_setup(interaction):
    """Quick setup wizard"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="⚡ Schnell-Setup Wizard",
        description="Schnelle Einrichtung des Bots für deinen Server:",
        color=0x2ecc71
    )
    
    embed.add_field(
        name="🚀 Setup-Optionen",
        value="• **Basis Setup** - Grundkonfiguration\n• **Gaming Server** - Gaming-Community Setup\n• **Business** - Geschäfts-Setup\n• **Community** - Community-Server Setup",
        inline=False
    )
    
    embed.add_field(
        name="📋 Was wird konfiguriert",
        value="• Rollen automatisch erstellen\n• Kategorien einrichten\n• Grundlegende Preise setzen\n• Zahlungsmethoden aktivieren",
        inline=False
    )
    
    quick_view = View(timeout=300)
    
    # Basic setup
    basic_button = Button(label="🏗️ Basis Setup", style=discord.ButtonStyle.success)
    basic_button.callback = lambda i: run_basic_setup(i)
    
    # Gaming setup
    gaming_button = Button(label="🎮 Gaming Setup", style=discord.ButtonStyle.primary)
    gaming_button.callback = lambda i: run_gaming_setup(i)
    
    # Business setup
    business_button = Button(label="💼 Business Setup", style=discord.ButtonStyle.primary)
    business_button.callback = lambda i: run_business_setup(i)
    
    # Community setup
    community_button = Button(label="👥 Community Setup", style=discord.ButtonStyle.secondary)
    community_button.callback = lambda i: run_community_setup(i)
    
    # Back button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.danger)
    back_button.callback = lambda i: show_admin_config(i)
    
    quick_view.add_item(basic_button)
    quick_view.add_item(gaming_button)
    quick_view.add_item(business_button)
    quick_view.add_item(community_button)
    quick_view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=quick_view, ephemeral=True)

async def show_export_import(interaction):
    """Export/Import configuration"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📤 Export/Import Konfiguration",
        description="Exportiere oder importiere Bot-Konfigurationen:",
        color=0x95a5a6
    )
    
    embed.add_field(
        name="📤 Export",
        value="• Aktuelle Konfiguration exportieren\n• Als JSON-Datei herunterladen\n• Backup erstellen",
        inline=True
    )
    
    embed.add_field(
        name="📥 Import",
        value="• Konfiguration aus Datei laden\n• Von anderem Server übernehmen\n• Backup wiederherstellen",
        inline=True
    )
    
    export_view = View(timeout=300)
    
    # Export button
    export_button = Button(label="📤 Konfiguration exportieren", style=discord.ButtonStyle.success)
    export_button.callback = lambda i: export_config(i)
    
    # Import button
    import_button = Button(label="📥 Konfiguration importieren", style=discord.ButtonStyle.primary)
    import_button.callback = lambda i: show_import_modal(i)
    
    # Reset button
    reset_button = Button(label="🔄 Auf Standard zurücksetzen", style=discord.ButtonStyle.danger)
    reset_button.callback = lambda i: reset_config(i)
    
    # Back button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_admin_config(i)
    
    export_view.add_item(export_button)
    export_view.add_item(import_button)
    export_view.add_item(reset_button)
    export_view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=export_view, ephemeral=True)

# ========================================
# MODAL IMPLEMENTATIONS FOR ADMIN PANEL
# ========================================

# Branding Modals
class BotNameModal(Modal):
    def __init__(self):
        super().__init__(title="🤖 Bot-Name ändern")
        self.bot_name = TextInput(
            label="Neuer Bot-Name",
            placeholder="z.B. Dein Server Bot, Custom Assistant...",
            required=True,
            max_length=50
        )
        self.add_item(self.bot_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        if "branding" not in server_config:
            server_config["branding"] = {}
        
        server_config["branding"]["bot_name"] = self.bot_name.value
        save_server_config(interaction.guild.id, server_config)
        
        await interaction.response.send_message(
            f"✅ Bot-Name erfolgreich geändert zu: **{self.bot_name.value}**",
            ephemeral=True
        )

class ColorModal(Modal):
    def __init__(self):
        super().__init__(title="🎨 Hauptfarbe ändern")
        self.color = TextInput(
            label="Hex Color Code",
            placeholder="z.B. #ff0000, #00ff00, #0066cc...",
            required=True,
            max_length=7
        )
        self.add_item(self.color)
    
    async def on_submit(self, interaction: discord.Interaction):
        color_value = self.color.value
        if not color_value.startswith('#'):
            color_value = '#' + color_value
        
        try:
            int(color_value[1:], 16)
        except ValueError:
            await interaction.response.send_message(
                "❌ Ungültiger Hex-Code! Verwende das Format #ff0000",
                ephemeral=True
            )
            return
        
        server_config = get_server_config(interaction.guild.id)
        if "branding" not in server_config:
            server_config["branding"] = {}
        
        server_config["branding"]["primary_color"] = color_value
        save_server_config(interaction.guild.id, server_config)
        
        await interaction.response.send_message(
            f"✅ Hauptfarbe erfolgreich geändert zu: **{color_value}**",
            ephemeral=True
        )

class FooterModal(Modal):
    def __init__(self):
        super().__init__(title="📝 Footer-Text bearbeiten")
        self.footer = TextInput(
            label="Footer-Text",
            placeholder="z.B. Dein Server • Bot System",
            required=True,
            max_length=100
        )
        self.add_item(self.footer)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        if "branding" not in server_config:
            server_config["branding"] = {}
        
        server_config["branding"]["footer_text"] = self.footer.value
        save_server_config(interaction.guild.id, server_config)
        
        await interaction.response.send_message(
            f"✅ Footer-Text erfolgreich geändert zu: **{self.footer.value}**",
            ephemeral=True
        )

# Role Configuration Modals
class AdminRoleModal(Modal):
    def __init__(self):
        super().__init__(title="👑 Admin-Rolle konfigurieren")
        self.role_name = TextInput(
            label="Admin-Rollen-Name",
            placeholder="z.B. Admin, Administrator, Owner...",
            required=True,
            max_length=50
        )
        self.add_item(self.role_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        if "roles" not in server_config:
            server_config["roles"] = {}
        
        server_config["roles"]["admin_role"] = self.role_name.value
        save_server_config(interaction.guild.id, server_config)
        
        await interaction.response.send_message(
            f"✅ Admin-Rolle erfolgreich geändert zu: **{self.role_name.value}**",
            ephemeral=True
        )

class StaffRoleModal(Modal):
    def __init__(self):
        super().__init__(title="🛠️ Staff-Rolle konfigurieren")
        self.role_name = TextInput(
            label="Staff-Rollen-Name",
            placeholder="z.B. Staff, Team, Moderator...",
            required=True,
            max_length=50
        )
        self.add_item(self.role_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        if "roles" not in server_config:
            server_config["roles"] = {}
        
        server_config["roles"]["staff_role"] = self.role_name.value
        save_server_config(interaction.guild.id, server_config)
        
        await interaction.response.send_message(
            f"✅ Staff-Rolle erfolgreich geändert zu: **{self.role_name.value}**",
            ephemeral=True
        )

class CustomerRoleModal(Modal):
    def __init__(self):
        super().__init__(title="👤 Kunden-Rolle konfigurieren")
        self.role_name = TextInput(
            label="Kunden-Rollen-Name",
            placeholder="z.B. Customer, Kunde, Client...",
            required=True,
            max_length=50
        )
        self.add_item(self.role_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        if "roles" not in server_config:
            server_config["roles"] = {}
        
        server_config["roles"]["customer_role"] = self.role_name.value
        save_server_config(interaction.guild.id, server_config)
        
        await interaction.response.send_message(
            f"✅ Kunden-Rolle erfolgreich geändert zu: **{self.role_name.value}**",
            ephemeral=True
        )

# Payment Configuration Modals
class PayPalModal(Modal):
    def __init__(self):
        super().__init__(title="💙 PayPal konfigurieren")
        self.email = TextInput(
            label="PayPal Email-Adresse",
            placeholder="z.B. business@example.com",
            required=True,
            max_length=100
        )
        self.add_item(self.email)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        if "payment" not in server_config:
            server_config["payment"] = {}
        
        server_config["payment"]["paypal_email"] = self.email.value
        save_server_config(interaction.guild.id, server_config)
        
        await interaction.response.send_message(
            f"✅ PayPal Email erfolgreich konfiguriert: **{self.email.value}**",
            ephemeral=True
        )

# Modal Show Functions
async def show_bot_name_modal(interaction):
    modal = BotNameModal()
    await interaction.response.send_modal(modal)

async def show_color_modal(interaction):
    modal = ColorModal()
    await interaction.response.send_modal(modal)

async def show_footer_modal(interaction):
    modal = FooterModal()
    await interaction.response.send_modal(modal)

async def show_admin_role_modal(interaction):
    modal = AdminRoleModal()
    await interaction.response.send_modal(modal)

async def show_staff_role_modal(interaction):
    modal = StaffRoleModal()
    await interaction.response.send_modal(modal)

async def show_customer_role_modal(interaction):
    modal = CustomerRoleModal()
    await interaction.response.send_modal(modal)

async def show_paypal_modal(interaction):
    modal = PayPalModal()
    await interaction.response.send_modal(modal)

# Placeholder functions for remaining modals (to prevent errors)
async def show_categories_config(interaction):
    """Zeige Kategorien-Konfiguration"""
    server_config = get_server_config(interaction.guild.id)
    categories = server_config.get("categories", {})
    
    embed = discord.Embed(
        title="📂 Kategorien-Konfiguration",
        description="Verwalte deine Ticket-Kategorien",
        color=0x0099ff
    )
    
    category_info = ""
    category_names = {
        "open": "📋 Offene Tickets",
        "claimed": "🔧 In Bearbeitung", 
        "paid": "💰 Bezahlt",
        "finished": "✅ Abgeschlossen"
    }
    
    for cat_key, cat_name in category_names.items():
        cat_id = categories.get(cat_key)
        if cat_id:
            try:
                category_channel = interaction.guild.get_channel(cat_id)
                if category_channel:
                    category_info += f"{cat_name}: {category_channel.mention}\n"
                else:
                    category_info += f"{cat_name}: ❌ Nicht gefunden (ID: {cat_id})\n"
            except:
                category_info += f"{cat_name}: ❌ Fehler beim Laden\n"
        else:
            category_info += f"{cat_name}: ❌ Nicht konfiguriert\n"
    
    embed.add_field(
        name="🏷️ Aktuelle Kategorien:",
        value=category_info if category_info else "Keine Kategorien konfiguriert",
        inline=False
    )
    
    # Buttons für Kategorie-Management
    view = View(timeout=300)
    
    # Kategorien bearbeiten
    edit_button = Button(label="✏️ Kategorien bearbeiten", style=discord.ButtonStyle.primary)
    edit_button.callback = lambda i: show_category_edit_modal(i)
    
    # Auto-Setup
    auto_button = Button(label="🚀 Auto-Setup", style=discord.ButtonStyle.success)
    auto_button.callback = lambda i: auto_setup_categories(i)
    
    # Zurück
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_admin_config(i)
    
    view.add_item(edit_button)
    view.add_item(auto_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def show_edit_prices_modal(interaction):
    """Zeige Preis-Editor"""
    server_config = get_server_config(interaction.guild.id)
    pricing = server_config.get("pricing", {})
    
    embed = discord.Embed(
        title="💰 Preis-Editor",
        description="Verwalte deine Service-Preise",
        color=0x00ff00
    )
    
    if pricing:
        price_list = ""
        for product, price in pricing.items():
            price_list += f"• **{product}:** {price:.2f}€\n"
        
        embed.add_field(
            name="📋 Aktuelle Preise:",
            value=price_list,
            inline=False
        )
    else:
        embed.add_field(
            name="📋 Aktuelle Preise:",
            value="Keine Preise konfiguriert",
            inline=False
        )
    
    # Buttons für Preis-Management
    view = View(timeout=300)
    
    # Preis hinzufügen
    add_button = Button(label="➕ Preis hinzufügen", style=discord.ButtonStyle.success)
    add_button.callback = lambda i: show_add_price_modal(i)
    
    # Preis bearbeiten
    edit_button = Button(label="✏️ Preis bearbeiten", style=discord.ButtonStyle.primary)
    edit_button.callback = lambda i: show_edit_existing_price(i)
    
    # Preis löschen
    delete_button = Button(label="🗑️ Preis löschen", style=discord.ButtonStyle.danger)
    delete_button.callback = lambda i: show_delete_price(i)
    
    # Zurück
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_admin_config(i)
    
    view.add_item(add_button)
    view.add_item(edit_button)
    view.add_item(delete_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Preis-Management Modals und Funktionen

class AddPriceModal(Modal):
    def __init__(self):
        super().__init__(title="➕ Neuen Preis hinzufügen")
        
        self.product_name = TextInput(
            label="Produkt/Service Name",
            placeholder="z.B. Custom Design, Premium Paket...",
            required=True,
            max_length=50
        )
        
        self.price = TextInput(
            label="Preis in Euro",
            placeholder="z.B. 25.99 oder 50",
            required=True,
            max_length=10
        )
        
        self.description = TextInput(
            label="Beschreibung (optional)",
            placeholder="Kurze Beschreibung des Services...",
            required=False,
            max_length=200,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.product_name)
        self.add_item(self.price)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            price_value = float(self.price.value.replace(",", "."))
            
            server_config = get_server_config(interaction.guild.id)
            if "pricing" not in server_config:
                server_config["pricing"] = {}
            
            server_config["pricing"][self.product_name.value] = price_value
            save_server_config(interaction.guild.id, server_config)
            
            embed = discord.Embed(
                title="✅ Preis hinzugefügt!",
                description=f"**{self.product_name.value}** wurde für **{price_value:.2f}€** hinzugefügt.",
                color=0x00ff00
            )
            
            if self.description.value:
                embed.add_field(
                    name="📝 Beschreibung:",
                    value=self.description.value,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Ungültiger Preis! Verwende nur Zahlen (z.B. 25.99)",
                ephemeral=True
            )

class EditPriceModal(Modal):
    def __init__(self, product_name, current_price):
        super().__init__(title=f"✏️ {product_name} bearbeiten")
        
        self.product_name = product_name
        
        self.new_name = TextInput(
            label="Neuer Produktname",
            default=product_name,
            required=True,
            max_length=50
        )
        
        self.new_price = TextInput(
            label="Neuer Preis in Euro",
            default=str(current_price),
            required=True,
            max_length=10
        )
        
        self.add_item(self.new_name)
        self.add_item(self.new_price)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            price_value = float(self.new_price.value.replace(",", "."))
            
            server_config = get_server_config(interaction.guild.id)
            
            # Alten Eintrag entfernen falls Name geändert wurde
            if self.product_name != self.new_name.value:
                if self.product_name in server_config.get("pricing", {}):
                    del server_config["pricing"][self.product_name]
            
            # Neuen/aktualisierten Eintrag hinzufügen
            if "pricing" not in server_config:
                server_config["pricing"] = {}
            
            server_config["pricing"][self.new_name.value] = price_value
            save_server_config(interaction.guild.id, server_config)
            
            embed = discord.Embed(
                title="✅ Preis aktualisiert!",
                description=f"**{self.new_name.value}** wurde auf **{price_value:.2f}€** aktualisiert.",
                color=0x00ff00
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Ungültiger Preis! Verwende nur Zahlen (z.B. 25.99)",
                ephemeral=True
            )

async def show_add_price_modal(interaction):
    modal = AddPriceModal()
    await interaction.response.send_modal(modal)

async def show_edit_existing_price(interaction):
    """Zeige Liste der bearbeitbaren Preise"""
    server_config = get_server_config(interaction.guild.id)
    pricing = server_config.get("pricing", {})
    
    if not pricing:
        await interaction.response.send_message(
            "❌ Keine Preise vorhanden! Füge erst einen Preis hinzu.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="✏️ Preis bearbeiten",
        description="Wähle den Preis, den du bearbeiten möchtest:",
        color=0x0099ff
    )
    
    view = View(timeout=300)
    
    # Buttons für jeden Preis (max 5 pro Reihe)
    button_count = 0
    for product, price in list(pricing.items())[:20]:  # Max 20 Produkte
        button = Button(
            label=f"{product} ({price:.2f}€)",
            style=discord.ButtonStyle.primary,
            custom_id=f"edit_price_{product}"
        )
        button.callback = lambda i, prod=product, pr=price: edit_specific_price(i, prod, pr)
        view.add_item(button)
        button_count += 1
    
    # Zurück Button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_edit_prices_modal(i)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def edit_specific_price(interaction, product_name, current_price):
    modal = EditPriceModal(product_name, current_price)
    await interaction.response.send_modal(modal)

async def show_delete_price(interaction):
    """Zeige Liste der löschbaren Preise"""
    server_config = get_server_config(interaction.guild.id)
    pricing = server_config.get("pricing", {})
    
    if not pricing:
        await interaction.response.send_message(
            "❌ Keine Preise vorhanden!",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="🗑️ Preis löschen",
        description="⚠️ **Welchen Preis möchtest du löschen?**",
        color=0xff0000
    )
    
    view = View(timeout=300)
    
    # Buttons für jeden Preis
    for product, price in list(pricing.items())[:20]:  # Max 20 Produkte
        button = Button(
            label=f"🗑️ {product} ({price:.2f}€)",
            style=discord.ButtonStyle.danger,
            custom_id=f"delete_price_{product}"
        )
        button.callback = lambda i, prod=product: confirm_delete_price(i, prod)
        view.add_item(button)
    
    # Zurück Button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_edit_prices_modal(i)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def confirm_delete_price(interaction, product_name):
    """Bestätigung für Preis-Löschung"""
    embed = discord.Embed(
        title="⚠️ Preis löschen bestätigen",
        description=f"Möchtest du **{product_name}** wirklich löschen?\n\n**Diese Aktion kann nicht rückgängig gemacht werden!**",
        color=0xff0000
    )
    
    view = View(timeout=60)
    
    # Bestätigen
    confirm_button = Button(label="🗑️ Ja, löschen", style=discord.ButtonStyle.danger)
    confirm_button.callback = lambda i: delete_price_confirmed(i, product_name)
    
    # Abbrechen
    cancel_button = Button(label="❌ Abbrechen", style=discord.ButtonStyle.secondary)
    cancel_button.callback = lambda i: show_delete_price(i)
    
    view.add_item(confirm_button)
    view.add_item(cancel_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def delete_price_confirmed(interaction, product_name):
    """Preis tatsächlich löschen"""
    server_config = get_server_config(interaction.guild.id)
    
    if product_name in server_config.get("pricing", {}):
        del server_config["pricing"][product_name]
        save_server_config(interaction.guild.id, server_config)
        
        embed = discord.Embed(
            title="✅ Preis gelöscht",
            description=f"**{product_name}** wurde erfolgreich entfernt.",
            color=0x00ff00
        )
    else:
        embed = discord.Embed(
            title="❌ Fehler",
            description=f"**{product_name}** wurde nicht gefunden.",
            color=0xff0000
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_add_product_modal(interaction):
    """Alias für Preis hinzufügen (gleiche Funktion)"""
    await show_add_price_modal(interaction)

async def show_pricing_categories_modal(interaction):
    """Preis-Kategorien Management"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    try:
        # Lade aktuelle Preis-Daten
        with open('prices.json', 'r', encoding='utf-8') as f:
            current_prices = json.load(f)
    except FileNotFoundError:
        current_prices = {}
    
    embed = discord.Embed(
        title="📁 Preis-Kategorien Management",
        description="Verwalte deine Produktkategorien und deren Preise:",
        color=0x9b59b6
    )
    
    # Zeige aktuelle Kategorien
    if current_prices:
        categories_text = ""
        for category, items in current_prices.items():
            if isinstance(items, dict):
                item_count = len(items)
                categories_text += f"• **{category}** ({item_count} Produkte)\n"
        
        embed.add_field(
            name="🗂️ Aktuelle Kategorien:",
            value=categories_text if categories_text else "Keine Kategorien gefunden",
            inline=False
        )
    else:
        embed.add_field(
            name="🗂️ Aktuelle Kategorien:",
            value="Noch keine Kategorien konfiguriert",
            inline=False
        )
    
    # Buttons für Kategorie-Management
    view = View(timeout=300)
    
    # Kategorie hinzufügen
    add_category_button = Button(label="➕ Kategorie hinzufügen", style=discord.ButtonStyle.success)
    add_category_button.callback = lambda i: show_add_category_modal(i)
    
    # Kategorie bearbeiten
    edit_category_button = Button(label="✏️ Kategorie bearbeiten", style=discord.ButtonStyle.primary)
    edit_category_button.callback = lambda i: show_edit_category_modal(i)
    
    # Standard-Setup
    default_setup_button = Button(label="🚀 Standard-Setup", style=discord.ButtonStyle.secondary)
    default_setup_button.callback = lambda i: setup_default_categories(i)
    
    # Zurück
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.danger)
    back_button.callback = lambda i: show_pricing_config(i)
    
    view.add_item(add_category_button)
    view.add_item(edit_category_button)
    view.add_item(default_setup_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ========================================
# ADDITIONAL CATEGORY MANAGEMENT FUNCTIONS
# ========================================

async def show_add_category_modal(interaction):
    """Modal für neue Kategorie hinzufügen"""
    modal = AddCategoryModal()
    await interaction.response.send_modal(modal)

async def show_edit_category_modal(interaction):
    """Interface für Kategorie bearbeiten"""
    try:
        with open('prices.json', 'r', encoding='utf-8') as f:
            current_prices = json.load(f)
    except FileNotFoundError:
        await interaction.response.send_message("❌ Keine Preisdaten gefunden!", ephemeral=True)
        return
    
    if not current_prices:
        await interaction.response.send_message("❌ Keine Kategorien vorhanden!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="✏️ Kategorie bearbeiten",
        description="Wähle eine Kategorie zum Bearbeiten:",
        color=0x3498db
    )
    
    view = View(timeout=300)
    
    # Buttons für jede Kategorie erstellen (max 25 Komponenten)
    button_count = 0
    for category in list(current_prices.keys())[:20]:  # Limit für Discord
        if button_count >= 20:
            break
        
        category_button = Button(
            label=f"✏️ {category}",
            style=discord.ButtonStyle.primary,
            row=button_count // 5  # 5 Buttons pro Reihe
        )
        category_button.callback = lambda i, cat=category: edit_category_items(i, cat)
        view.add_item(category_button)
        button_count += 1
    
    # Zurück-Button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_pricing_categories_modal(i)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def edit_category_items(interaction, category_name):
    """Bearbeite Items einer Kategorie"""
    try:
        with open('prices.json', 'r', encoding='utf-8') as f:
            current_prices = json.load(f)
    except FileNotFoundError:
        await interaction.response.send_message("❌ Preisdaten nicht gefunden!", ephemeral=True)
        return
    
    category_items = current_prices.get(category_name, {})
    
    embed = discord.Embed(
        title=f"✏️ {category_name} bearbeiten",
        description=f"Verwalte die Produkte in der Kategorie **{category_name}**:",
        color=0xe74c3c
    )
    
    if isinstance(category_items, dict) and category_items:
        items_text = ""
        for item, price in category_items.items():
            items_text += f"• **{item}**: {price}\n"
        
        embed.add_field(
            name="📦 Aktuelle Produkte:",
            value=items_text,
            inline=False
        )
    else:
        embed.add_field(
            name="📦 Aktuelle Produkte:",
            value="Keine Produkte in dieser Kategorie",
            inline=False
        )
    
    view = View(timeout=300)
    
    # Produkt hinzufügen
    add_item_button = Button(label="➕ Produkt hinzufügen", style=discord.ButtonStyle.success)
    add_item_button.callback = lambda i: show_add_item_to_category_modal(i, category_name)
    
    # Kategorie löschen
    delete_category_button = Button(label="🗑️ Kategorie löschen", style=discord.ButtonStyle.danger)
    delete_category_button.callback = lambda i: confirm_delete_category(i, category_name)
    
    # Zurück
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_edit_category_modal(i)
    
    view.add_item(add_item_button)
    view.add_item(delete_category_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup_default_categories(interaction):
    """Setup Standard-Kategorien für Haze Visuals"""
    default_categories = {
        "Clothing": {
            "Custom T-Shirt": "15€",
            "Custom Hoodie": "25€", 
            "Custom Cap": "12€",
            "Custom Jacke": "35€"
        },
        "Clothing Packages": {
            "Basis Paket": "45€",
            "Premium Paket": "65€",
            "Deluxe Paket": "85€"
        },
        "Biker Packages": {
            "Biker Weste Custom": "30€",
            "Komplette Biker Ausrüstung": "120€",
            "Biker Patches": "8€"
        },
        "Chains": {
            "Custom Kette": "20€",
            "Premium Kette": "35€",
            "Gravierte Kette": "45€"
        },
        "Weaponskins": {
            "FiveM Weapon Skin": "10€",
            "Premium Weapon Pack": "25€",
            "Custom Weapon Design": "15€"
        }
    }
    
    # Speichere Standard-Kategorien
    try:
        with open('prices.json', 'w', encoding='utf-8') as f:
            json.dump(default_categories, f, indent=2, ensure_ascii=False)
        
        embed = discord.Embed(
            title="✅ Standard-Setup abgeschlossen",
            description="Die Standard-Kategorien für Haze Visuals wurden erfolgreich eingerichtet!",
            color=0x00ff00
        )
        
        categories_text = ""
        for category, items in default_categories.items():
            item_count = len(items)
            categories_text += f"• **{category}** ({item_count} Produkte)\n"
        
        embed.add_field(
            name="📁 Eingerichtete Kategorien:",
            value=categories_text,
            inline=False
        )
        
        print("✅ Standard-Preiskategorien eingerichtet")
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Fehler beim Setup",
            description=f"Es gab einen Fehler beim Einrichten: {str(e)}",
            color=0xff0000
        )
        print(f"❌ Fehler beim Standard-Setup: {e}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_add_item_to_category_modal(interaction, category_name):
    """Modal zum Hinzufügen eines Items zu einer Kategorie"""
    modal = AddItemToCategoryModal(category_name)
    await interaction.response.send_modal(modal)

async def confirm_delete_category(interaction, category_name):
    """Bestätigung für Kategorie löschen"""
    embed = discord.Embed(
        title="⚠️ Kategorie löschen",
        description=f"Möchtest du die Kategorie **{category_name}** wirklich löschen?\n\n**Diese Aktion kann nicht rückgängig gemacht werden!**",
        color=0xff0000
    )
    
    view = View(timeout=300)
    
    # Bestätigen
    confirm_button = Button(label="✅ Ja, löschen", style=discord.ButtonStyle.danger)
    confirm_button.callback = lambda i: delete_category_confirmed(i, category_name)
    
    # Abbrechen
    cancel_button = Button(label="❌ Abbrechen", style=discord.ButtonStyle.secondary)
    cancel_button.callback = lambda i: show_edit_category_modal(i)
    
    view.add_item(confirm_button)
    view.add_item(cancel_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def delete_category_confirmed(interaction, category_name):
    """Kategorie tatsächlich löschen"""
    try:
        with open('prices.json', 'r', encoding='utf-8') as f:
            current_prices = json.load(f)
        
        if category_name in current_prices:
            del current_prices[category_name]
            
            with open('prices.json', 'w', encoding='utf-8') as f:
                json.dump(current_prices, f, indent=2, ensure_ascii=False)
            
            embed = discord.Embed(
                title="✅ Kategorie gelöscht",
                description=f"Kategorie **{category_name}** wurde erfolgreich entfernt.",
                color=0x00ff00
            )
            print(f"✅ Kategorie gelöscht: {category_name}")
        else:
            embed = discord.Embed(
                title="❌ Fehler",
                description=f"Kategorie **{category_name}** wurde nicht gefunden.",
                color=0xff0000
            )
    except Exception as e:
        embed = discord.Embed(
            title="❌ Fehler beim Löschen",
            description=f"Fehler: {str(e)}",
            color=0xff0000
        )
        print(f"❌ Fehler beim Löschen der Kategorie: {e}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

class AddCategoryModal(Modal):
    """Modal für neue Kategorie hinzufügen"""
    def __init__(self):
        super().__init__(title="➕ Neue Kategorie hinzufügen")
        
        self.category_name = TextInput(
            label="Kategorie-Name",
            placeholder="z.B. Clothing, Weapons, Services...",
            required=True,
            max_length=50
        )
        
        self.first_item = TextInput(
            label="Erstes Produkt (optional)",
            placeholder="z.B. Custom T-Shirt",
            required=False,
            max_length=100
        )
        
        self.first_price = TextInput(
            label="Preis für erstes Produkt (optional)",
            placeholder="z.B. 15€ oder 15.99",
            required=False,
            max_length=20
        )
        
        self.add_item(self.category_name)
        self.add_item(self.first_item)
        self.add_item(self.first_price)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Lade aktuelle Preise
            try:
                with open('prices.json', 'r', encoding='utf-8') as f:
                    current_prices = json.load(f)
            except FileNotFoundError:
                current_prices = {}
            
            category_name = self.category_name.value.strip()
            
            # Prüfe ob Kategorie bereits existiert
            if category_name in current_prices:
                await interaction.response.send_message(
                    f"❌ Kategorie **{category_name}** existiert bereits!",
                    ephemeral=True
                )
                return
            
            # Erstelle neue Kategorie
            current_prices[category_name] = {}
            
            # Füge erstes Produkt hinzu falls angegeben
            if self.first_item.value.strip() and self.first_price.value.strip():
                item_name = self.first_item.value.strip()
                price_value = self.first_price.value.strip()
                current_prices[category_name][item_name] = price_value
            
            # Speichere Änderungen
            with open('prices.json', 'w', encoding='utf-8') as f:
                json.dump(current_prices, f, indent=2, ensure_ascii=False)
            
            embed = discord.Embed(
                title="✅ Kategorie hinzugefügt",
                description=f"Kategorie **{category_name}** wurde erfolgreich erstellt!",
                color=0x00ff00
            )
            
            if self.first_item.value.strip():
                embed.add_field(
                    name="📦 Erstes Produkt:",
                    value=f"**{self.first_item.value}** - {self.first_price.value}",
                    inline=False
                )
            
            print(f"✅ Neue Kategorie erstellt: {category_name}")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Fehler",
                description=f"Fehler beim Erstellen der Kategorie: {str(e)}",
                color=0xff0000
            )
            print(f"❌ Fehler beim Erstellen der Kategorie: {e}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AddItemToCategoryModal(Modal):
    """Modal zum Hinzufügen eines Items zu einer Kategorie"""
    def __init__(self, category_name):
        self.category_name = category_name
        super().__init__(title=f"➕ Produkt zu {category_name} hinzufügen")
        
        self.item_name = TextInput(
            label="Produkt-Name",
            placeholder="z.B. Custom T-Shirt, Premium Service...",
            required=True,
            max_length=100
        )
        
        self.item_price = TextInput(
            label="Preis",
            placeholder="z.B. 15€ oder 15.99",
            required=True,
            max_length=20
        )
        
        self.item_description = TextInput(
            label="Beschreibung (optional)",
            placeholder="Kurze Beschreibung des Produkts...",
            required=False,
            max_length=200,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.item_name)
        self.add_item(self.item_price)
        self.add_item(self.item_description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Lade aktuelle Preise
            with open('prices.json', 'r', encoding='utf-8') as f:
                current_prices = json.load(f)
            
            if self.category_name not in current_prices:
                await interaction.response.send_message(
                    f"❌ Kategorie **{self.category_name}** nicht gefunden!",
                    ephemeral=True
                )
                return
            
            item_name = self.item_name.value.strip()
            price_value = self.item_price.value.strip()
            
            # Prüfe ob Item bereits existiert
            if item_name in current_prices[self.category_name]:
                await interaction.response.send_message(
                    f"❌ Produkt **{item_name}** existiert bereits in **{self.category_name}**!",
                    ephemeral=True
                )
                return
            
            # Füge neues Item hinzu
            current_prices[self.category_name][item_name] = price_value
            
            # Speichere Änderungen
            with open('prices.json', 'w', encoding='utf-8') as f:
                json.dump(current_prices, f, indent=2, ensure_ascii=False)
            
            embed = discord.Embed(
                title="✅ Produkt hinzugefügt",
                description=f"**{item_name}** wurde erfolgreich zu **{self.category_name}** hinzugefügt!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📦 Neues Produkt:",
                value=f"**{item_name}** - {price_value}",
                inline=False
            )
            
            if self.item_description.value.strip():
                embed.add_field(
                    name="📝 Beschreibung:",
                    value=self.item_description.value,
                    inline=False
                )
            
            print(f"✅ Neues Produkt hinzugefügt: {item_name} in {self.category_name}")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Fehler",
                description=f"Fehler beim Hinzufügen des Produkts: {str(e)}",
                color=0xff0000
            )
            print(f"❌ Fehler beim Hinzufügen des Produkts: {e}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ========================================
# DISCOUNT-SYSTEM IMPLEMENTIERUNG
# ========================================

async def show_add_discount_modal(interaction):
    """Zeige Discount hinzufügen Modal"""
    modal = AddDiscountModal()
    await interaction.response.send_modal(modal)

async def show_remove_discount_modal(interaction):
    """Zeige Discount entfernen Interface"""
    discount_codes = load_discount_codes()
    
    if not discount_codes:
        await interaction.response.send_message(
            "❌ Keine Discount-Codes vorhanden!",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="🗑️ Discount-Code entfernen",
        description="Wähle den Code, den du löschen möchtest:",
        color=0xff0000
    )
    
    # Zeige aktuelle Codes
    code_list = ""
    for code, data in discount_codes.items():
        discount_percent = data.get('discount', 0)
        uses = data.get('uses', 0)
        max_uses = data.get('max_uses', 'Unbegrenzt')
        code_list += f"• **{code}**: {discount_percent}% ({uses}/{max_uses} verwendet)\n"
    
    embed.add_field(
        name="📋 Aktuelle Codes:",
        value=code_list[:1024],  # Discord embed limit
        inline=False
    )
    
    view = View(timeout=300)
    
    # Buttons für jeden Code (max 20)
    for code in list(discount_codes.keys())[:20]:
        button = Button(
            label=f"🗑️ {code}",
            style=discord.ButtonStyle.danger,
            custom_id=f"remove_discount_{code}"
        )
        button.callback = lambda i, c=code: confirm_remove_discount(i, c)
        view.add_item(button)
    
    # Zurück Button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_admin_config(i)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def show_bulk_discount_modal(interaction):
    """Zeige Bulk Discount Management"""
    embed = discord.Embed(
        title="📦 Bulk Discount Management",
        description="Massenbearbeitung von Discount-Codes",
        color=0x0099ff
    )
    
    discount_codes = load_discount_codes()
    
    embed.add_field(
        name="📊 Statistiken:",
        value=f"• **Aktive Codes:** {len(discount_codes)}\n• **Gesamte Nutzungen:** {sum(code.get('uses', 0) for code in discount_codes.values())}",
        inline=False
    )
    
    view = View(timeout=300)
    
    # Alle Codes deaktivieren
    disable_button = Button(label="🚫 Alle deaktivieren", style=discord.ButtonStyle.danger)
    disable_button.callback = lambda i: bulk_disable_discounts(i)
    
    # Nutzungszähler zurücksetzen
    reset_button = Button(label="🔄 Nutzungen zurücksetzen", style=discord.ButtonStyle.primary)
    reset_button.callback = lambda i: bulk_reset_uses(i)
    
    # Export Codes
    export_button = Button(label="📤 Codes exportieren", style=discord.ButtonStyle.secondary)
    export_button.callback = lambda i: export_discount_codes(i)
    
    # Zurück
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_admin_config(i)
    
    view.add_item(disable_button)
    view.add_item(reset_button)
    view.add_item(export_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class AddDiscountModal(Modal):
    def __init__(self):
        super().__init__(title="🎫 Neuen Discount-Code erstellen")
        
        self.code_name = TextInput(
            label="Code-Name",
            placeholder="z.B. WELCOME20, SUMMER2024...",
            required=True,
            max_length=20
        )
        
        self.discount_percent = TextInput(
            label="Rabatt in Prozent",
            placeholder="z.B. 10, 25, 50...",
            required=True,
            max_length=3
        )
        
        self.max_uses = TextInput(
            label="Maximale Nutzungen (leer = unbegrenzt)",
            placeholder="z.B. 100, 500...",
            required=False,
            max_length=10
        )
        
        self.description = TextInput(
            label="Beschreibung (optional)",
            placeholder="Beschreibung des Codes...",
            required=False,
            max_length=100,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.code_name)
        self.add_item(self.discount_percent)
        self.add_item(self.max_uses)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validierung
            code = self.code_name.value.upper().strip()
            discount = int(self.discount_percent.value)
            
            if discount < 1 or discount > 100:
                await interaction.response.send_message(
                    "❌ Rabatt muss zwischen 1 und 100 Prozent liegen!",
                    ephemeral=True
                )
                return
            
            max_uses = None
            if self.max_uses.value.strip():
                max_uses = int(self.max_uses.value.strip())
                if max_uses < 1:
                    await interaction.response.send_message(
                        "❌ Maximale Nutzungen muss mindestens 1 sein!",
                        ephemeral=True
                    )
                    return
            
            # Code erstellen
            discount_codes = load_discount_codes()
            
            if code in discount_codes:
                await interaction.response.send_message(
                    f"❌ Code **{code}** existiert bereits!",
                    ephemeral=True
                )
                return
            
            # Neuen Code hinzufügen
            discount_codes[code] = {
                'discount': discount,
                'uses': 0,
                'max_uses': max_uses,
                'description': self.description.value.strip(),
                'created_at': datetime.now().isoformat(),
                'created_by': interaction.user.id
            }
            
            save_discount_codes(discount_codes)
            
            embed = discord.Embed(
                title="✅ Discount-Code erstellt!",
                description=f"**{code}** wurde erfolgreich erstellt.",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📋 Details:",
                value=f"• **Rabatt:** {discount}%\n• **Max. Nutzungen:** {max_uses if max_uses else 'Unbegrenzt'}\n• **Beschreibung:** {self.description.value or 'Keine'}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Ungültige Eingabe! Überprüfe deine Zahlen.",
                ephemeral=True
            )

async def confirm_remove_discount(interaction, code):
    """Bestätigung für Discount-Code Löschung"""
    embed = discord.Embed(
        title="⚠️ Discount-Code löschen",
        description=f"Möchtest du den Code **{code}** wirklich löschen?\n\n**Diese Aktion kann nicht rückgängig gemacht werden!**",
        color=0xff0000
    )
    
    view = View(timeout=60)
    
    # Bestätigen
    confirm_button = Button(label="🗑️ Ja, löschen", style=discord.ButtonStyle.danger)
    confirm_button.callback = lambda i: delete_discount_confirmed(i, code)
    
    # Abbrechen
    cancel_button = Button(label="❌ Abbrechen", style=discord.ButtonStyle.secondary)
    cancel_button.callback = lambda i: show_remove_discount_modal(i)
    
    view.add_item(confirm_button)
    view.add_item(cancel_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def delete_discount_confirmed(interaction, code):
    """Discount-Code tatsächlich löschen"""
    discount_codes = load_discount_codes()
    
    if code in discount_codes:
        del discount_codes[code]
        save_discount_codes(discount_codes)
        
        embed = discord.Embed(
            title="✅ Code gelöscht",
            description=f"**{code}** wurde erfolgreich entfernt.",
            color=0x00ff00
        )
    else:
        embed = discord.Embed(
            title="❌ Fehler",
            description=f"**{code}** wurde nicht gefunden.",
            color=0xff0000
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def bulk_disable_discounts(interaction):
    """Alle Discount-Codes deaktivieren"""
    embed = discord.Embed(
        title="⚠️ Alle Codes deaktivieren",
        description="**ACHTUNG:** Möchtest du wirklich ALLE Discount-Codes löschen?\n\n**Diese Aktion kann nicht rückgängig gemacht werden!**",
        color=0xff0000
    )
    
    view = View(timeout=60)
    
    confirm_button = Button(label="🗑️ Ja, alle löschen", style=discord.ButtonStyle.danger)
    confirm_button.callback = lambda i: confirm_bulk_disable(i)
    
    cancel_button = Button(label="❌ Abbrechen", style=discord.ButtonStyle.secondary)
    cancel_button.callback = lambda i: show_bulk_discount_modal(i)
    
    view.add_item(confirm_button)
    view.add_item(cancel_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def confirm_bulk_disable(interaction):
    """Alle Codes tatsächlich löschen"""
    save_discount_codes({})  # Leeres Dictionary = alle Codes gelöscht
    
    embed = discord.Embed(
        title="✅ Alle Codes gelöscht",
        description="Alle Discount-Codes wurden erfolgreich entfernt.",
        color=0x00ff00
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def bulk_reset_uses(interaction):
    """Nutzungszähler aller Codes zurücksetzen"""
    discount_codes = load_discount_codes()
    
    if not discount_codes:
        await interaction.response.send_message(
            "❌ Keine Codes vorhanden!",
            ephemeral=True
        )
        return
    
    # Nutzungszähler zurücksetzen
    for code in discount_codes:
        discount_codes[code]['uses'] = 0
    
    save_discount_codes(discount_codes)
    
    embed = discord.Embed(
        title="✅ Nutzungen zurückgesetzt",
        description=f"Nutzungszähler für alle {len(discount_codes)} Codes wurden auf 0 zurückgesetzt.",
        color=0x00ff00
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def export_discount_codes(interaction):
    """Discount-Codes exportieren"""
    discount_codes = load_discount_codes()
    
    if not discount_codes:
        await interaction.response.send_message(
            "❌ Keine Codes zum Exportieren vorhanden!",
            ephemeral=True
        )
        return
    
    # Export-Text erstellen
    export_text = "# Discount-Codes Export\n\n"
    for code, data in discount_codes.items():
        export_text += f"**{code}**\n"
        export_text += f"- Rabatt: {data.get('discount', 0)}%\n"
        export_text += f"- Nutzungen: {data.get('uses', 0)}/{data.get('max_uses', 'Unbegrenzt')}\n"
        export_text += f"- Beschreibung: {data.get('description', 'Keine')}\n"
        export_text += f"- Erstellt: {data.get('created_at', 'Unbekannt')}\n\n"
    
    embed = discord.Embed(
        title="📤 Codes exportiert",
        description=f"Export von {len(discount_codes)} Discount-Codes:",
        color=0x0099ff
    )
    
    # Text in Datei schreiben (simuliert)
    embed.add_field(
        name="📋 Export-Daten:",
        value=export_text[:1000] + ("..." if len(export_text) > 1000 else ""),
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Zahlungsoptionen-System

async def show_bank_modal(interaction):
    """Zeige Bank-Konfiguration"""
    modal = BankConfigModal()
    await interaction.response.send_modal(modal)

async def show_additional_payment_modal(interaction):
    """Zeige zusätzliche Zahlungsmethoden"""
    server_config = get_server_config(interaction.guild.id)
    payment_config = server_config.get("payment", {})
    
    embed = discord.Embed(
        title="💳 Zahlungsmethoden verwalten",
        description="Konfiguriere alle verfügbaren Zahlungsoptionen",
        color=0x0099ff
    )
    
    # Aktuelle Zahlungsmethoden anzeigen
    payment_info = ""
    
    # PayPal
    paypal_email = payment_config.get("paypal_email", "Nicht konfiguriert")
    payment_info += f"💙 **PayPal:** {paypal_email}\n"
    
    # Paysafecard
    paysafe_enabled = payment_config.get("paysafecard_enabled", False)
    payment_info += f"🟢 **Paysafecard:** {'✅ Aktiviert' if paysafe_enabled else '❌ Deaktiviert'}\n"
    
    # Bank Transfer
    bank_name = payment_config.get("bank_name", "Nicht konfiguriert")
    payment_info += f"🏦 **Banküberweisung:** {bank_name}\n"
    
    # Crypto
    crypto_enabled = payment_config.get("crypto_enabled", False)
    payment_info += f"₿ **Kryptowährung:** {'✅ Aktiviert' if crypto_enabled else '❌ Deaktiviert'}\n"
    
    embed.add_field(
        name="💳 Aktuelle Zahlungsmethoden:",
        value=payment_info,
        inline=False
    )
    
    view = View(timeout=300)
    
    # PayPal konfigurieren
    paypal_button = Button(label="💙 PayPal bearbeiten", style=discord.ButtonStyle.primary)
    paypal_button.callback = lambda i: show_paypal_modal(i)
    
    # Bank konfigurieren
    bank_button = Button(label="🏦 Bank bearbeiten", style=discord.ButtonStyle.primary)
    bank_button.callback = lambda i: show_bank_modal(i)
    
    # Alternative Methoden
    alt_button = Button(label="🔄 Weitere Optionen", style=discord.ButtonStyle.secondary)
    alt_button.callback = lambda i: show_alternative_payments(i)
    
    # Neue Zahlungsmethoden
    new_methods_button = Button(label="⭐ Neue Zahlungsmethoden", style=discord.ButtonStyle.secondary)
    new_methods_button.callback = lambda i: show_new_payment_methods(i)
    
    # Zurück
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_admin_config(i)
    
    view.add_item(paypal_button)
    view.add_item(bank_button)
    view.add_item(alt_button)
    view.add_item(new_methods_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class BankConfigModal(Modal):
    def __init__(self):
        super().__init__(title="🏦 Bank-Konfiguration")
        
        server_config = get_server_config_for_modal()
        payment_config = server_config.get("payment", {})
        
        self.bank_name = TextInput(
            label="Bank-Name",
            placeholder="z.B. Deutsche Bank, Sparkasse...",
            default=payment_config.get("bank_name", ""),
            required=False,
            max_length=50
        )
        
        self.account_holder = TextInput(
            label="Kontoinhaber",
            placeholder="Vor- und Nachname des Kontoinhabers",
            default=payment_config.get("account_holder", ""),
            required=False,
            max_length=100
        )
        
        self.iban = TextInput(
            label="IBAN",
            placeholder="DE89 3704 0044 0532 0130 00",
            default=payment_config.get("iban", ""),
            required=False,
            max_length=34
        )
        
        self.bic = TextInput(
            label="BIC/SWIFT (optional)",
            placeholder="z.B. COBADEFFXXX",
            default=payment_config.get("bic", ""),
            required=False,
            max_length=11
        )
        
        self.add_item(self.bank_name)
        self.add_item(self.account_holder)
        self.add_item(self.iban)
        self.add_item(self.bic)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        
        if "payment" not in server_config:
            server_config["payment"] = {}
        
        # Bank-Daten speichern
        server_config["payment"]["bank_name"] = self.bank_name.value.strip()
        server_config["payment"]["account_holder"] = self.account_holder.value.strip()
        server_config["payment"]["iban"] = self.iban.value.strip()
        server_config["payment"]["bic"] = self.bic.value.strip()
        
        save_server_config(interaction.guild.id, server_config)
        
        embed = discord.Embed(
            title="✅ Bank-Konfiguration gespeichert!",
            description="Bankverbindung wurde erfolgreich aktualisiert.",
            color=0x00ff00
        )
        
        if self.bank_name.value.strip():
            embed.add_field(
                name="🏦 Bank-Details:",
                value=f"• **Bank:** {self.bank_name.value}\n• **Inhaber:** {self.account_holder.value}\n• **IBAN:** {self.iban.value[:8]}****",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_alternative_payments(interaction):
    """Zeige alternative Zahlungsmethoden"""
    server_config = get_server_config(interaction.guild.id)
    payment_config = server_config.get("payment", {})
    
    embed = discord.Embed(
        title="🔄 Alternative Zahlungsmethoden",
        description="Aktiviere/Deaktiviere weitere Zahlungsoptionen",
        color=0x0099ff
    )
    
    # Status der alternativen Methoden
    paysafe_enabled = payment_config.get("paysafecard_enabled", False)
    crypto_enabled = payment_config.get("crypto_enabled", False)
    cash_enabled = payment_config.get("cash_enabled", False)
    
    status_info = f"""
🟢 **Paysafecard:** {'✅ Aktiviert' if paysafe_enabled else '❌ Deaktiviert'}
₿ **Kryptowährung:** {'✅ Aktiviert' if crypto_enabled else '❌ Deaktiviert'}
💵 **Barzahlung:** {'✅ Aktiviert' if cash_enabled else '❌ Deaktiviert'}
    """
    
    embed.add_field(
        name="💳 Status:",
        value=status_info.strip(),
        inline=False
    )
    
    view = View(timeout=300)
    
    # Paysafecard Toggle
    paysafe_style = discord.ButtonStyle.success if paysafe_enabled else discord.ButtonStyle.secondary
    paysafe_label = "🟢 Paysafecard deaktivieren" if paysafe_enabled else "🟢 Paysafecard aktivieren"
    paysafe_button = Button(label=paysafe_label, style=paysafe_style)
    paysafe_button.callback = lambda i: toggle_payment_method(i, "paysafecard_enabled")
    
    # Crypto Toggle
    crypto_style = discord.ButtonStyle.success if crypto_enabled else discord.ButtonStyle.secondary
    crypto_label = "₿ Crypto deaktivieren" if crypto_enabled else "₿ Crypto aktivieren"
    crypto_button = Button(label=crypto_label, style=crypto_style)
    crypto_button.callback = lambda i: toggle_payment_method(i, "crypto_enabled")
    
    # Cash Toggle
    cash_style = discord.ButtonStyle.success if cash_enabled else discord.ButtonStyle.secondary
    cash_label = "💵 Cash deaktivieren" if cash_enabled else "💵 Cash aktivieren"
    cash_button = Button(label=cash_label, style=cash_style)
    cash_button.callback = lambda i: toggle_payment_method(i, "cash_enabled")
    
    # Crypto Adressen
    crypto_config_button = Button(label="₿ Crypto Adressen", style=discord.ButtonStyle.primary)
    crypto_config_button.callback = lambda i: show_crypto_config_modal(i)
    
    # Zurück
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_additional_payment_modal(i)
    
    view.add_item(paysafe_button)
    view.add_item(crypto_button)
    view.add_item(cash_button)
    view.add_item(crypto_config_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def toggle_payment_method(interaction, method_key):
    """Toggle eine Zahlungsmethode an/aus"""
    server_config = get_server_config(interaction.guild.id)
    
    if "payment" not in server_config:
        server_config["payment"] = {}
    
    # Toggle Status
    current_status = server_config["payment"].get(method_key, False)
    server_config["payment"][method_key] = not current_status
    
    save_server_config(interaction.guild.id, server_config)
    
    # Status-Text
    method_names = {
        "paysafecard_enabled": "Paysafecard",
        "crypto_enabled": "Kryptowährung", 
        "cash_enabled": "Barzahlung"
    }
    
    method_name = method_names.get(method_key, method_key)
    new_status = "aktiviert" if not current_status else "deaktiviert"
    
    embed = discord.Embed(
        title=f"✅ {method_name} {new_status}",
        description=f"{method_name} wurde erfolgreich {new_status}.",
        color=0x00ff00 if not current_status else 0xff9900
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

class CryptoConfigModal(Modal):
    def __init__(self):
        super().__init__(title="₿ Krypto-Adressen konfigurieren")
        
        server_config = get_server_config_for_modal()
        crypto_config = server_config.get("payment", {}).get("crypto", {})
        
        self.bitcoin_address = TextInput(
            label="Bitcoin (BTC) Adresse",
            placeholder="bc1q...",
            default=crypto_config.get("bitcoin", ""),
            required=False,
            max_length=100
        )
        
        self.ethereum_address = TextInput(
            label="Ethereum (ETH) Adresse",
            placeholder="0x...",
            default=crypto_config.get("ethereum", ""),
            required=False,
            max_length=100
        )
        
        self.usdt_address = TextInput(
            label="USDT (Tether) Adresse",
            placeholder="TRC20 oder ERC20 Adresse...",
            default=crypto_config.get("usdt", ""),
            required=False,
            max_length=100
        )
        
        self.add_item(self.bitcoin_address)
        self.add_item(self.ethereum_address)
        self.add_item(self.usdt_address)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        
        if "payment" not in server_config:
            server_config["payment"] = {}
        if "crypto" not in server_config["payment"]:
            server_config["payment"]["crypto"] = {}
        
        # Crypto-Adressen speichern
        server_config["payment"]["crypto"]["bitcoin"] = self.bitcoin_address.value.strip()
        server_config["payment"]["crypto"]["ethereum"] = self.ethereum_address.value.strip()
        server_config["payment"]["crypto"]["usdt"] = self.usdt_address.value.strip()
        
        save_server_config(interaction.guild.id, server_config)
        
        embed = discord.Embed(
            title="✅ Krypto-Adressen gespeichert!",
            description="Kryptowährungs-Adressen wurden erfolgreich aktualisiert.",
            color=0x00ff00
        )
        
        crypto_info = ""
        if self.bitcoin_address.value.strip():
            crypto_info += f"₿ **Bitcoin:** {self.bitcoin_address.value[:8]}...\n"
        if self.ethereum_address.value.strip():
            crypto_info += f"⚡ **Ethereum:** {self.ethereum_address.value[:8]}...\n"
        if self.usdt_address.value.strip():
            crypto_info += f"💵 **USDT:** {self.usdt_address.value[:8]}...\n"
        
        if crypto_info:
            embed.add_field(
                name="₿ Konfigurierte Adressen:",
                value=crypto_info,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_crypto_config_modal(interaction):
    modal = CryptoConfigModal()
    await interaction.response.send_modal(modal)

def get_server_config_for_modal():
    """Helper function für Modals"""
    # Einfache Implementierung - kann erweitert werden
    return {}

# Neue Zahlungsmethoden Management
async def show_new_payment_methods(interaction):
    """Zeige neue Zahlungsmethoden Konfiguration"""
    server_config = get_server_config(interaction.guild.id)
    payment_config = server_config.get("payment", {})
    
    embed = discord.Embed(
        title="⭐ Neue Zahlungsmethoden",
        description="Konfiguriere erweiterte Zahlungsoptionen für deine Kunden",
        color=0x0099ff
    )
    
    # Status der neuen Zahlungsmethoden
    status_info = ""
    
    # Tebex
    tebex_domain = payment_config.get("tebex_domain", "Nicht konfiguriert")
    status_info += f"🛒 **Tebex:** {tebex_domain}\n"
    
    # Amazon Giftcard
    amazon_enabled = payment_config.get("amazon_enabled", False)
    status_info += f"📦 **Amazon Giftcard:** {'✅ Aktiviert' if amazon_enabled else '❌ Deaktiviert'}\n"
    
    # Netflix Card
    netflix_enabled = payment_config.get("netflix_enabled", False)
    status_info += f"🎬 **Netflix Card:** {'✅ Aktiviert' if netflix_enabled else '❌ Deaktiviert'}\n"
    
    # Credit Card
    cc_site = payment_config.get("creditcard_site", "Nicht konfiguriert")
    status_info += f"💳 **Credit Card:** {cc_site}\n"
    
    # Enhanced Crypto
    btc_wallet = payment_config.get("crypto", {}).get("bitcoin_wallet", "Nicht konfiguriert")
    eth_wallet = payment_config.get("crypto", {}).get("ethereum_wallet", "Nicht konfiguriert")
    status_info += f"₿ **Bitcoin:** {btc_wallet[:8]}...{'✅' if len(btc_wallet) > 20 else '❌'}\n"
    status_info += f"⚡ **Ethereum:** {eth_wallet[:8]}...{'✅' if len(eth_wallet) > 20 else '❌'}\n"
    
    embed.add_field(
        name="📊 Status:",
        value=status_info,
        inline=False
    )
    
    view = View(timeout=300)
    
    # Tebex konfigurieren
    tebex_button = Button(label="🛒 Tebex Setup", style=discord.ButtonStyle.primary)
    tebex_button.callback = lambda i: show_tebex_config_modal(i)
    
    # Giftcards Toggle
    giftcards_button = Button(label="🎁 Giftcards verwalten", style=discord.ButtonStyle.primary)
    giftcards_button.callback = lambda i: show_giftcards_config(i)
    
    # Credit Card Setup
    cc_button = Button(label="💳 Credit Card Setup", style=discord.ButtonStyle.primary)
    cc_button.callback = lambda i: show_creditcard_config_modal(i)
    
    # Enhanced Crypto Setup
    crypto_button = Button(label="₿ Crypto Wallets", style=discord.ButtonStyle.primary)
    crypto_button.callback = lambda i: show_enhanced_crypto_config_modal(i)
    
    # Zurück
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_additional_payment_modal(i)
    
    view.add_item(tebex_button)
    view.add_item(giftcards_button)
    view.add_item(cc_button)
    view.add_item(crypto_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Tebex Konfiguration
class TebexConfigModal(Modal):
    def __init__(self):
        super().__init__(title="🛒 Tebex Shop Konfiguration")
        
        server_config = get_server_config_for_modal()
        payment_config = server_config.get("payment", {})
        
        self.tebex_domain = TextInput(
            label="Tebex Shop Domain",
            placeholder="z.B. shop.minecraft-server.de",
            default=payment_config.get("tebex_domain", ""),
            required=True,
            max_length=100
        )
        
        self.add_item(self.tebex_domain)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        
        if "payment" not in server_config:
            server_config["payment"] = {}
        
        server_config["payment"]["tebex_domain"] = self.tebex_domain.value.strip()
        server_config["payment"]["tebex_enabled"] = True
        
        save_server_config(interaction.guild.id, server_config)
        
        embed = discord.Embed(
            title="✅ Tebex Shop konfiguriert!",
            description=f"Tebex Shop Domain: **{self.tebex_domain.value}**\n\nKunden können jetzt Tebex-Codes als Zahlungsmethode verwenden.",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_tebex_config_modal(interaction):
    modal = TebexConfigModal()
    await interaction.response.send_modal(modal)

# Giftcards Konfiguration
async def show_giftcards_config(interaction):
    """Zeige Giftcard-Optionen"""
    server_config = get_server_config(interaction.guild.id)
    payment_config = server_config.get("payment", {})
    
    embed = discord.Embed(
        title="🎁 Giftcard Optionen",
        description="Aktiviere/Deaktiviere Giftcard-Zahlungen",
        color=0x0099ff
    )
    
    amazon_enabled = payment_config.get("amazon_enabled", False)
    netflix_enabled = payment_config.get("netflix_enabled", False)
    
    status_info = f"""
📦 **Amazon Giftcards:** {'✅ Aktiviert' if amazon_enabled else '❌ Deaktiviert'}
🎬 **Netflix Cards:** {'✅ Aktiviert' if netflix_enabled else '❌ Deaktiviert'}
    """
    
    embed.add_field(
        name="📊 Status:",
        value=status_info.strip(),
        inline=False
    )
    
    view = View(timeout=300)
    
    # Amazon Toggle
    amazon_style = discord.ButtonStyle.success if amazon_enabled else discord.ButtonStyle.secondary
    amazon_label = "📦 Amazon deaktivieren" if amazon_enabled else "📦 Amazon aktivieren"
    amazon_button = Button(label=amazon_label, style=amazon_style)
    amazon_button.callback = lambda i: toggle_giftcard_method(i, "amazon_enabled")
    
    # Netflix Toggle
    netflix_style = discord.ButtonStyle.success if netflix_enabled else discord.ButtonStyle.secondary
    netflix_label = "🎬 Netflix deaktivieren" if netflix_enabled else "🎬 Netflix aktivieren"
    netflix_button = Button(label=netflix_label, style=netflix_style)
    netflix_button.callback = lambda i: toggle_giftcard_method(i, "netflix_enabled")
    
    # Zurück
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_new_payment_methods(i)
    
    view.add_item(amazon_button)
    view.add_item(netflix_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def toggle_giftcard_method(interaction, method_key):
    """Toggle Giftcard-Methode an/aus"""
    server_config = get_server_config(interaction.guild.id)
    
    if "payment" not in server_config:
        server_config["payment"] = {}
    
    current_status = server_config["payment"].get(method_key, False)
    server_config["payment"][method_key] = not current_status
    
    save_server_config(interaction.guild.id, server_config)
    
    method_names = {
        "amazon_enabled": "Amazon Giftcards",
        "netflix_enabled": "Netflix Cards"
    }
    
    method_name = method_names.get(method_key, method_key)
    new_status = "aktiviert" if not current_status else "deaktiviert"
    
    embed = discord.Embed(
        title=f"✅ {method_name} {new_status}",
        description=f"{method_name} wurde erfolgreich {new_status}.",
        color=0x00ff00 if not current_status else 0xff9900
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Credit Card Konfiguration
class CreditCardConfigModal(Modal):
    def __init__(self):
        super().__init__(title="💳 Credit Card Konfiguration")
        
        server_config = get_server_config_for_modal()
        payment_config = server_config.get("payment", {})
        
        self.cc_number = TextInput(
            label="Credit Card Nummer",
            placeholder="z.B. 1234 5678 9012 3456",
            default=payment_config.get("creditcard_number", ""),
            required=False,
            max_length=20
        )
        
        self.payment_site = TextInput(
            label="Payment Website",
            placeholder="z.B. stripe.com/payments/xyz123",
            default=payment_config.get("creditcard_site", ""),
            required=True,
            max_length=200
        )
        
        self.add_item(self.cc_number)
        self.add_item(self.payment_site)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        
        if "payment" not in server_config:
            server_config["payment"] = {}
        
        server_config["payment"]["creditcard_number"] = self.cc_number.value.strip()
        server_config["payment"]["creditcard_site"] = self.payment_site.value.strip()
        server_config["payment"]["creditcard_enabled"] = True
        
        save_server_config(interaction.guild.id, server_config)
        
        embed = discord.Embed(
            title="✅ Credit Card konfiguriert!",
            description=f"Payment-Site: **{self.payment_site.value}**\n\nKunden können jetzt per Credit Card zahlen.",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_creditcard_config_modal(interaction):
    modal = CreditCardConfigModal()
    await interaction.response.send_modal(modal)

# Enhanced Crypto Konfiguration
class EnhancedCryptoConfigModal(Modal):
    def __init__(self):
        super().__init__(title="₿ Enhanced Crypto Wallets")
        
        server_config = get_server_config_for_modal()
        crypto_config = server_config.get("payment", {}).get("crypto", {})
        
        self.bitcoin_wallet = TextInput(
            label="Bitcoin Wallet Adresse",
            placeholder="bc1q... oder 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            default=crypto_config.get("bitcoin_wallet", ""),
            required=False,
            max_length=100
        )
        
        self.ethereum_wallet = TextInput(
            label="Ethereum Wallet Adresse",
            placeholder="0x742d35Cc6634C0532925a3b8D9C0AC9c",
            default=crypto_config.get("ethereum_wallet", ""),
            required=False,
            max_length=100
        )
        
        self.add_item(self.bitcoin_wallet)
        self.add_item(self.ethereum_wallet)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        
        if "payment" not in server_config:
            server_config["payment"] = {}
        if "crypto" not in server_config["payment"]:
            server_config["payment"]["crypto"] = {}
        
        server_config["payment"]["crypto"]["bitcoin_wallet"] = self.bitcoin_wallet.value.strip()
        server_config["payment"]["crypto"]["ethereum_wallet"] = self.ethereum_wallet.value.strip()
        server_config["payment"]["enhanced_crypto_enabled"] = True
        
        save_server_config(interaction.guild.id, server_config)
        
        embed = discord.Embed(
            title="✅ Enhanced Crypto Wallets konfiguriert!",
            description="Crypto-Zahlungen mit Real-time Kursen sind jetzt verfügbar.",
            color=0x00ff00
        )
        
        crypto_info = ""
        if self.bitcoin_wallet.value.strip():
            crypto_info += f"₿ **Bitcoin:** {self.bitcoin_wallet.value[:8]}...\n"
        if self.ethereum_wallet.value.strip():
            crypto_info += f"⚡ **Ethereum:** {self.ethereum_wallet.value[:8]}...\n"
        
        if crypto_info:
            embed.add_field(
                name="₿ Konfigurierte Wallets:",
                value=crypto_info,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def show_enhanced_crypto_config_modal(interaction):
    modal = EnhancedCryptoConfigModal()
    await interaction.response.send_modal(modal)

# Payment Toggle Management
async def show_payment_toggles(interaction):
    """Zeige Payment Toggle Interface"""
    server_config = get_server_config(interaction.guild.id)
    payment_config = server_config.get("payment", {})
    
    embed = discord.Embed(
        title="⚡ Zahlungsmethoden verwalten",
        description="Aktiviere oder deaktiviere Zahlungsmethoden für deine Kunden",
        color=0x9b59b6
    )
    
    # Status aller Zahlungsmethoden
    status_info = ""
    
    # Standard-Methoden
    paypal_enabled = payment_config.get("paypal_enabled", True)
    bank_enabled = payment_config.get("bank_enabled", True) 
    paysafe_enabled = payment_config.get("paysafe_enabled", True)
    
    status_info += f"💙 **PayPal:** {'✅ Aktiviert' if paypal_enabled else '❌ Deaktiviert'}\n"
    status_info += f"🏦 **Bank Transfer:** {'✅ Aktiviert' if bank_enabled else '❌ Deaktiviert'}\n"
    status_info += f"💳 **Paysafecard:** {'✅ Aktiviert' if paysafe_enabled else '❌ Deaktiviert'}\n"
    status_info += "\n**🎯 Erweiterte Methoden:**\n"
    
    # Erweiterte Methoden
    tebex_enabled = payment_config.get("tebex_enabled", False)
    amazon_enabled = payment_config.get("amazon_enabled", False)
    netflix_enabled = payment_config.get("netflix_enabled", False)
    cc_enabled = payment_config.get("creditcard_enabled", False)
    crypto_enabled = payment_config.get("enhanced_crypto_enabled", False)
    
    status_info += f"🛒 **Tebex Code:** {'✅ Aktiviert' if tebex_enabled else '❌ Deaktiviert'}\n"
    status_info += f"📦 **Amazon Giftcard:** {'✅ Aktiviert' if amazon_enabled else '❌ Deaktiviert'}\n"
    status_info += f"🎬 **Netflix Card:** {'✅ Aktiviert' if netflix_enabled else '❌ Deaktiviert'}\n"
    status_info += f"💳 **Credit Card:** {'✅ Aktiviert' if cc_enabled else '❌ Deaktiviert'}\n"
    status_info += f"₿ **Enhanced Crypto:** {'✅ Aktiviert' if crypto_enabled else '❌ Deaktiviert'}\n"
    
    embed.add_field(
        name="📊 Status:",
        value=status_info,
        inline=False
    )
    
    view = View(timeout=300)
    
    # Standard-Methoden Toggle Buttons (Row 1)
    paypal_style = discord.ButtonStyle.success if paypal_enabled else discord.ButtonStyle.secondary
    paypal_label = "💙 PayPal AUS" if paypal_enabled else "💙 PayPal AN"
    paypal_button = Button(label=paypal_label, style=paypal_style)
    paypal_button.callback = lambda i: toggle_standard_payment_method(i, "paypal_enabled")
    
    bank_style = discord.ButtonStyle.success if bank_enabled else discord.ButtonStyle.secondary
    bank_label = "🏦 Bank AUS" if bank_enabled else "🏦 Bank AN"
    bank_button = Button(label=bank_label, style=bank_style)
    bank_button.callback = lambda i: toggle_standard_payment_method(i, "bank_enabled")
    
    paysafe_style = discord.ButtonStyle.success if paysafe_enabled else discord.ButtonStyle.secondary
    paysafe_label = "💳 Paysafe AUS" if paysafe_enabled else "💳 Paysafe AN"
    paysafe_button = Button(label=paysafe_label, style=paysafe_style)
    paysafe_button.callback = lambda i: toggle_standard_payment_method(i, "paysafe_enabled")
    
    # Erweiterte Methoden Toggle Buttons (Row 2)
    tebex_style = discord.ButtonStyle.success if tebex_enabled else discord.ButtonStyle.secondary
    tebex_label = "🛒 Tebex AUS" if tebex_enabled else "🛒 Tebex AN"
    tebex_button = Button(label=tebex_label, style=tebex_style)
    tebex_button.callback = lambda i: toggle_standard_payment_method(i, "tebex_enabled")
    
    amazon_style = discord.ButtonStyle.success if amazon_enabled else discord.ButtonStyle.secondary
    amazon_label = "📦 Amazon AUS" if amazon_enabled else "📦 Amazon AN"
    amazon_button = Button(label=amazon_label, style=amazon_style)
    amazon_button.callback = lambda i: toggle_standard_payment_method(i, "amazon_enabled")
    
    # Row 3
    netflix_style = discord.ButtonStyle.success if netflix_enabled else discord.ButtonStyle.secondary
    netflix_label = "🎬 Netflix AUS" if netflix_enabled else "🎬 Netflix AN"
    netflix_button = Button(label=netflix_label, style=netflix_style)
    netflix_button.callback = lambda i: toggle_standard_payment_method(i, "netflix_enabled")
    
    cc_style = discord.ButtonStyle.success if cc_enabled else discord.ButtonStyle.secondary
    cc_label = "💳 CC AUS" if cc_enabled else "💳 CC AN"
    cc_button = Button(label=cc_label, style=cc_style)
    cc_button.callback = lambda i: toggle_standard_payment_method(i, "creditcard_enabled")
    
    crypto_style = discord.ButtonStyle.success if crypto_enabled else discord.ButtonStyle.secondary
    crypto_label = "₿ Crypto AUS" if crypto_enabled else "₿ Crypto AN"
    crypto_button = Button(label=crypto_label, style=crypto_style)
    crypto_button.callback = lambda i: toggle_standard_payment_method(i, "enhanced_crypto_enabled")
    
    # Zurück Button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_payment_config(i)
    
    # Buttons hinzufügen
    view.add_item(paypal_button)
    view.add_item(bank_button)
    view.add_item(paysafe_button)
    view.add_item(tebex_button)
    view.add_item(amazon_button)
    view.add_item(netflix_button)
    view.add_item(cc_button)
    view.add_item(crypto_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def toggle_standard_payment_method(interaction, method_key):
    """Toggle Standard-Zahlungsmethode an/aus"""
    server_config = get_server_config(interaction.guild.id)
    
    if "payment" not in server_config:
        server_config["payment"] = {}
    
    # Standard ist True für Standard-Methoden
    default_value = True if method_key in ["paypal_enabled", "bank_enabled", "paysafe_enabled"] else False
    current_status = server_config["payment"].get(method_key, default_value)
    server_config["payment"][method_key] = not current_status
    
    save_server_config(interaction.guild.id, server_config)
    
    method_names = {
        "paypal_enabled": "PayPal",
        "bank_enabled": "Bank Transfer",
        "paysafe_enabled": "Paysafecard",
        "tebex_enabled": "Tebex Code",
        "amazon_enabled": "Amazon Giftcard",
        "netflix_enabled": "Netflix Card",
        "creditcard_enabled": "Credit Card",
        "enhanced_crypto_enabled": "Enhanced Crypto"
    }
    
    method_name = method_names.get(method_key, method_key)
    new_status = "aktiviert" if not current_status else "deaktiviert"
    
    embed = discord.Embed(
        title=f"✅ {method_name} {new_status}",
        description=f"{method_name} wurde erfolgreich {new_status}.",
        color=0x00ff00 if not current_status else 0xff9900
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Auto-Update System
BOT_VERSION = "2.5.0"  # Update this when making changes
LAST_UPDATE_HASH = None

@tasks.loop(hours=1)  # Check for updates every hour
async def check_for_updates():
    """Check for bot updates automatically"""
    try:
        # Get current file hash
        current_hash = get_bot_file_hash()
        
        global LAST_UPDATE_HASH
        if LAST_UPDATE_HASH is None:
            LAST_UPDATE_HASH = current_hash
            return
        
        if current_hash != LAST_UPDATE_HASH:
            print(f"🔄 Bot-Update erkannt! Neue Version: {BOT_VERSION}")
            
            # Update all Discord components
            await update_all_ticket_panels()
            await notify_admins_about_update()
            
            LAST_UPDATE_HASH = current_hash
            
    except Exception as e:
        print(f"⚠️ Update-Check Fehler: {e}")

def get_bot_file_hash():
    """Get hash of main bot file to detect changes"""
    try:
        with open(__file__, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return None

async def update_all_ticket_panels():
    """Update all ticket panels across all servers"""
    try:
        updated_servers = 0
        
        for guild in bot.guilds:
            try:
                # Find existing ticket panels and update them
                server_config = get_server_config(guild.id)
                panel_channel_id = server_config.get("ticket_panel_channel_id")
                
                if panel_channel_id:
                    channel = guild.get_channel(panel_channel_id)
                    if channel:
                        # Delete old panel messages
                        async for message in channel.history(limit=10):
                            if message.author == bot.user:
                                try:
                                    await message.delete()
                                except:
                                    pass
                        
                        # Create new updated panel
                        await create_ticket_panel_in_channel(channel)
                        updated_servers += 1
                        
                        print(f"✅ Ticket-Panel aktualisiert für: {guild.name}")
                        
            except Exception as e:
                print(f"⚠️ Panel-Update Fehler für {guild.name}: {e}")
        
        print(f"🎯 {updated_servers} Server-Panels erfolgreich aktualisiert")
        
    except Exception as e:
        print(f"❌ Panel-Update Fehler: {e}")

async def notify_admins_about_update():
    """Notify server admins about bot updates"""
    try:
        update_embed = discord.Embed(
            title="🚀 Bot automatisch aktualisiert!",
            description=f"**Version:** {BOT_VERSION}\n\n✅ **Neue Features verfügbar:**\n• Verbesserte Zahlungsmethoden\n• Erweiterte Admin-Funktionen\n• Performance-Optimierungen\n\n🎯 **Ticket-Panels wurden automatisch aktualisiert**",
            color=0x00ff00
        )
        update_embed.set_footer(text="Automatisches Update-System • Keine Aktion erforderlich")
        
        notified_guilds = 0
        
        for guild in bot.guilds:
            try:
                # Find admin or system channel
                admin_channel = None
                
                # Try to find a system/admin channel
                for channel in guild.text_channels:
                    if any(keyword in channel.name.lower() for keyword in ['admin', 'bot', 'system', 'log']):
                        admin_channel = channel
                        break
                
                # Fallback to first available channel
                if not admin_channel:
                    admin_channel = next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
                
                if admin_channel:
                    await admin_channel.send(embed=update_embed)
                    notified_guilds += 1
                    
            except Exception as e:
                print(f"⚠️ Benachrichtigung Fehler für {guild.name}: {e}")
        
        print(f"📢 {notified_guilds} Server über Update benachrichtigt")
        
    except Exception as e:
        print(f"❌ Admin-Benachrichtigung Fehler: {e}")

async def create_ticket_panel_in_channel(channel):
    """Create ticket panel in specified channel"""
    try:
        # Create the updated ticket panel
        embed = discord.Embed(
            title="🎫 Haze Visuals Support",
            description="Willkommen beim Haze Visuals Support-System!\n\nWähle die passende Kategorie für dein Anliegen:",
            color=0x2ecc71
        )
        embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        embed.set_footer(text=f"Haze Visuals Bot v{BOT_VERSION} • Automatisch aktualisiert")
        
        # Create ticket buttons
        ticket_view = View(timeout=None)
        
        categories = [
            ("🛒 Bestellung", "clothing", "Bestelle Custom Clothing"),
            ("📦 Fertige Pakete", "finished", "Fertige Designs & Support"),
            ("🐛 Bug Report", "bug", "Melde einen Fehler"),
            ("💡 Vorschlag", "suggestion", "Teile deine Ideen mit"),
            ("📝 Bewerbung", "application", "Bewirb dich bei unserem Team")
        ]
        
        for label, category, description in categories:
            button = Button(label=label, style=discord.ButtonStyle.primary)
            button.callback = create_ticket_callback(category)
            ticket_view.add_item(button)
        
        # Send with banner
        banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        await channel.send(embed=embed, view=ticket_view, file=banner_file)
        
        # Save panel channel ID
        server_config = get_server_config(channel.guild.id)
        server_config["ticket_panel_channel_id"] = channel.id
        save_server_config(channel.guild.id, server_config)
        
    except Exception as e:
        print(f"❌ Panel-Erstellung Fehler: {e}")

def create_ticket_callback(ticket_type):
    """Create callback for ticket creation"""
    async def ticket_callback(interaction):
        await handle_ticket_creation(interaction, ticket_type)
    return ticket_callback

# Manual Update Command für Admins
@bot.tree.command(name="force_update", description="Erzwinge Bot-Update (nur für Administratoren)")
async def force_update_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Nur Administratoren können Updates erzwingen.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🔄 Update wird erzwungen...",
        description="Bot-Update wird gestartet. Dies kann einige Sekunden dauern.",
        color=0xffa500
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Trigger update
    try:
        await update_all_ticket_panels()
        await notify_admins_about_update()
        
        success_embed = discord.Embed(
            title="✅ Update erfolgreich!",
            description=f"Bot wurde auf Version {BOT_VERSION} aktualisiert.",
            color=0x00ff00
        )
        
        await interaction.followup.send(embed=success_embed, ephemeral=True)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Update fehlgeschlagen",
            description=f"Fehler: {str(e)}",
            color=0xff0000
        )
        
        await interaction.followup.send(embed=error_embed, ephemeral=True)

# ========================================
# GIVEAWAY SYSTEM
# ========================================

# Global storage for active giveaways
active_giveaways = {}

@bot.tree.command(name="giveaway", description="Erstelle ein Giveaway mit automatischem Countdown und Gewinner-Auswahl")
async def giveaway_command(interaction: discord.Interaction):
    """Create a giveaway with automatic countdown and winner selection"""
    
    # Check admin permissions
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ Du benötigst 'Server verwalten' Berechtigung für diesen Befehl.", 
            ephemeral=True
        )
        return
    
    # Show giveaway setup modal
    modal = GiveawaySetupModal()
    await interaction.response.send_modal(modal)

class GiveawaySetupModal(Modal):
    def __init__(self):
        super().__init__(title="🎉 Giveaway erstellen")
        
        self.prize = TextInput(
            label="🎁 Preis",
            placeholder="z.B. Discord Nitro, 50€ Steam Guthaben, Custom Bot...",
            required=True,
            max_length=200
        )
        
        self.duration = TextInput(
            label="⏰ Dauer (in Minuten)",
            placeholder="z.B. 60 für 1 Stunde, 1440 für 24 Stunden",
            required=True,
            max_length=10
        )
        
        self.description = TextInput(
            label="📝 Beschreibung (optional)",
            placeholder="Zusätzliche Informationen über das Giveaway...",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        
        self.requirements = TextInput(
            label="📋 Teilnahmebedingungen (optional)",
            placeholder="z.B. Server-Level 5, seit 1 Woche Mitglied...",
            required=False,
            max_length=300
        )
        
        self.add_item(self.prize)
        self.add_item(self.duration)
        self.add_item(self.description)
        self.add_item(self.requirements)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate duration
            try:
                duration_minutes = int(self.duration.value)
                if duration_minutes < 1 or duration_minutes > 10080:  # Max 1 week
                    await interaction.response.send_message("❌ Dauer muss zwischen 1 Minute und 1 Woche (10080 Minuten) liegen.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ Ungültige Dauer. Bitte gib eine Zahl in Minuten ein.", ephemeral=True)
                return
            
            # Calculate end time
            end_time = datetime.now(pytz.UTC) + timedelta(minutes=duration_minutes)
            
            # Create giveaway
            await create_giveaway(
                interaction,
                self.prize.value,
                end_time,
                self.description.value or None,
                self.requirements.value or None
            )
            
        except Exception as e:
            print(f"❌ Giveaway Setup Error: {e}")
            await interaction.response.send_message(f"❌ Fehler beim Erstellen des Giveaways: {str(e)}", ephemeral=True)

async def create_giveaway(interaction, prize, end_time, description=None, requirements=None):
    """Create giveaway channel and message"""
    try:
        guild = interaction.guild
        
        # Create giveaway channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                send_messages=False,
                add_reactions=True,
                read_messages=True
            ),
            guild.me: discord.PermissionOverwrite(
                send_messages=True,
                read_messages=True,
                manage_messages=True
            )
        }
        
        # Add permissions for staff roles
        hv_team_role = discord.utils.get(guild.roles, name="HV | Team")
        hv_leitung_role = discord.utils.get(guild.roles, name="HV | Leitung")
        
        if hv_team_role:
            overwrites[hv_team_role] = discord.PermissionOverwrite(
                send_messages=True,
                read_messages=True,
                manage_messages=True
            )
        
        if hv_leitung_role:
            overwrites[hv_leitung_role] = discord.PermissionOverwrite(
                send_messages=True,
                read_messages=True,
                manage_messages=True
            )
        
        # Create channel with timestamp
        channel_name = f"🎉-giveaway-{datetime.now().strftime('%m%d-%H%M')}"
        giveaway_channel = await guild.create_text_channel(
            name=channel_name,
            topic=f"🎁 Giveaway: {prize} | Läuft bis {end_time.strftime('%d.%m.%Y %H:%M')} UTC",
            overwrites=overwrites,
            reason=f"Giveaway erstellt von {interaction.user.display_name}"
        )
        
        # Create giveaway embed
        time_left = end_time - datetime.now(pytz.UTC)
        hours, remainder = divmod(int(time_left.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        
        embed = discord.Embed(
            title="🎉 GIVEAWAY LÄUFT!",
            description=f"**🎁 Preis:** {prize}\n\n**⏰ Endet:** <t:{int(end_time.timestamp())}:R>\n**📅 Endzeit:** <t:{int(end_time.timestamp())}:F>",
            color=0xff6b35
        )
        
        if description:
            embed.add_field(
                name="📝 Beschreibung:",
                value=description,
                inline=False
            )
        
        if requirements:
            embed.add_field(
                name="📋 Teilnahmebedingungen:",
                value=requirements,
                inline=False
            )
        
        embed.add_field(
            name="🎯 Teilnahme:",
            value="Reagiere mit 🎉 um teilzunehmen!",
            inline=False
        )
        
        embed.add_field(
            name="👥 Teilnehmer:",
            value="0",
            inline=True
        )
        
        embed.add_field(
            name="🏆 Gewinner:",
            value="Wird automatisch ausgewählt",
            inline=True
        )
        
        embed.set_footer(text=f"Erstellt von {interaction.user.display_name} • Haze Visuals Bot")
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1234567890123456789.png")  # You can replace with actual emoji URL
        
        # Send giveaway message
        giveaway_message = await giveaway_channel.send("@everyone 🎉 **NEUES GIVEAWAY!** 🎉", embed=embed)
        
        # Add reaction
        await giveaway_message.add_reaction("🎉")
        
        # Store giveaway data
        giveaway_id = f"{guild.id}_{giveaway_channel.id}_{giveaway_message.id}"
        active_giveaways[giveaway_id] = {
            "guild_id": guild.id,
            "channel_id": giveaway_channel.id,
            "message_id": giveaway_message.id,
            "prize": prize,
            "end_time": end_time,
            "description": description,
            "requirements": requirements,
            "creator": interaction.user.id,
            "participants": set(),
            "ended": False
        }
        
        # Start countdown task
        asyncio.create_task(giveaway_countdown(giveaway_id))
        
        # Confirm creation
        success_embed = discord.Embed(
            title="✅ Giveaway erfolgreich erstellt!",
            description=f"**Channel:** {giveaway_channel.mention}\n**Preis:** {prize}\n**Läuft bis:** <t:{int(end_time.timestamp())}:F>",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=success_embed, ephemeral=True)
        print(f"✅ Giveaway erstellt: {giveaway_id}")
        
    except Exception as e:
        print(f"❌ Giveaway Creation Error: {e}")
        await interaction.response.send_message(f"❌ Fehler beim Erstellen des Giveaways: {str(e)}", ephemeral=True)

async def giveaway_countdown(giveaway_id):
    """Handle giveaway countdown and winner selection"""
    try:
        giveaway_data = active_giveaways.get(giveaway_id)
        if not giveaway_data:
            return
        
        while datetime.now(pytz.UTC) < giveaway_data["end_time"] and not giveaway_data["ended"]:
            # Update every 60 seconds
            await asyncio.sleep(60)
            
            # Update participant count
            await update_giveaway_participants(giveaway_id)
        
        # End giveaway
        if not giveaway_data["ended"]:
            await end_giveaway(giveaway_id)
            
    except Exception as e:
        print(f"❌ Giveaway Countdown Error: {e}")

async def update_giveaway_participants(giveaway_id):
    """Update participant count in giveaway message"""
    try:
        giveaway_data = active_giveaways.get(giveaway_id)
        if not giveaway_data or giveaway_data["ended"]:
            return
        
        guild = bot.get_guild(giveaway_data["guild_id"])
        if not guild:
            return
        
        channel = guild.get_channel(giveaway_data["channel_id"])
        if not channel:
            return
        
        try:
            message = await channel.fetch_message(giveaway_data["message_id"])
        except discord.NotFound:
            return
        
        # Get reaction users
        participants = set()
        for reaction in message.reactions:
            if str(reaction.emoji) == "🎉":
                async for user in reaction.users():
                    if not user.bot:
                        participants.add(user.id)
                break
        
        # Update stored participants
        giveaway_data["participants"] = participants
        
        # Update embed
        embed = message.embeds[0]
        
        # Find and update participant count field
        for i, field in enumerate(embed.fields):
            if field.name == "👥 Teilnehmer:":
                embed.set_field_at(i, name="👥 Teilnehmer:", value=str(len(participants)), inline=True)
                break
        
        await message.edit(embed=embed)
        
    except Exception as e:
        print(f"❌ Participant Update Error: {e}")

async def end_giveaway(giveaway_id):
    """End giveaway and select winner"""
    try:
        giveaway_data = active_giveaways.get(giveaway_id)
        if not giveaway_data or giveaway_data["ended"]:
            return
        
        giveaway_data["ended"] = True
        
        guild = bot.get_guild(giveaway_data["guild_id"])
        if not guild:
            return
        
        channel = guild.get_channel(giveaway_data["channel_id"])
        if not channel:
            return
        
        try:
            message = await channel.fetch_message(giveaway_data["message_id"])
        except discord.NotFound:
            return
        
        # Get final participants
        await update_giveaway_participants(giveaway_id)
        participants = list(giveaway_data["participants"])
        
        if not participants:
            # No participants
            embed = discord.Embed(
                title="🎉 GIVEAWAY BEENDET",
                description=f"**🎁 Preis:** {giveaway_data['prize']}\n\n❌ **Keine Teilnehmer!**\nLeider hat niemand an diesem Giveaway teilgenommen.",
                color=0xff0000
            )
            embed.set_footer(text="Haze Visuals Bot • Giveaway System")
            
            await message.edit(embed=embed)
            await channel.send("😢 Das Giveaway ist ohne Teilnehmer zu Ende gegangen.")
            
        else:
            # Select winner
            winner_id = random.choice(participants)
            winner = guild.get_member(winner_id)
            
            if winner:
                # Update message
                embed = discord.Embed(
                    title="🎉 GIVEAWAY BEENDET!",
                    description=f"**🎁 Preis:** {giveaway_data['prize']}\n\n🏆 **Gewinner:** {winner.mention}\n👥 **Teilnehmer:** {len(participants)}",
                    color=0xffd700
                )
                embed.set_footer(text="Herzlichen Glückwunsch! • Haze Visuals Bot")
                
                await message.edit(embed=embed)
                
                # Send winner DM
                try:
                    dm_embed = discord.Embed(
                        title="🎉 Du hast gewonnen!",
                        description=f"**Glückwunsch!** Du hast das Giveaway gewonnen!\n\n**🎁 Preis:** {giveaway_data['prize']}\n**🏠 Server:** {guild.name}\n\nDas Team wird sich bald bei dir melden!",
                        color=0xffd700
                    )
                    dm_embed.set_footer(text="Haze Visuals Bot • Giveaway Gewinner")
                    
                    await winner.send(embed=dm_embed)
                    print(f"✅ Winner DM sent to {winner.display_name}")
                    
                except discord.Forbidden:
                    await channel.send(f"⚠️ {winner.mention} Konnte dir keine DM senden! Bitte melde dich bei einem Admin.")
                
                # Announce in channel
                winner_announcement = discord.Embed(
                    title="🏆 GEWINNER VERKÜNDET!",
                    description=f"**{winner.mention} hat gewonnen!**\n\n🎁 **Preis:** {giveaway_data['prize']}\n🎯 **Aus {len(participants)} Teilnehmern ausgewählt**",
                    color=0xffd700
                )
                
                await channel.send(embed=winner_announcement)
                
                # Post in winner channel if configured
                await post_winner_announcement(guild, winner, giveaway_data['prize'], len(participants))
                
        # Clean up
        del active_giveaways[giveaway_id]
        print(f"✅ Giveaway beendet: {giveaway_id}")
        
    except Exception as e:
        print(f"❌ End Giveaway Error: {e}")

async def post_winner_announcement(guild, winner, prize, total_participants):
    """Post winner announcement in configured winner channel"""
    try:
        server_config = get_server_config(guild.id)
        winner_channel_id = server_config.get("channels", {}).get("winner_channel")
        
        if not winner_channel_id:
            return
        
        winner_channel = guild.get_channel(winner_channel_id)
        if not winner_channel:
            return
        
        embed = discord.Embed(
            title="🏆 GIVEAWAY GEWINNER!",
            description=f"**Gewinner:** {winner.mention}\n**Preis:** {prize}\n**Teilnehmer:** {total_participants}",
            color=0xffd700
        )
        embed.set_thumbnail(url=winner.avatar.url if winner.avatar else winner.default_avatar.url)
        embed.set_footer(text=f"Gewonnen am {datetime.now().strftime('%d.%m.%Y um %H:%M')} • Haze Visuals Bot")
        
        await winner_channel.send(f"🎉 **NEUER GIVEAWAY GEWINNER!** 🎉", embed=embed)
        
    except Exception as e:
        print(f"⚠️ Winner Channel Post Error: {e}")

# Real-time Crypto Price API
async def get_crypto_prices():
    """Hole aktuelle Crypto-Preise von CoinGecko API"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        'ids': 'bitcoin,ethereum',
        'vs_currencies': 'eur',
        'include_24hr_change': 'true'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'bitcoin': data['bitcoin']['eur'],
                        'ethereum': data['ethereum']['eur'],
                        'btc_change': data['bitcoin'].get('eur_24h_change', 0),
                        'eth_change': data['ethereum'].get('eur_24h_change', 0)
                    }
                else:
                    print(f"⚠️ CoinGecko API Error: {response.status}")
                    return None
    except Exception as e:
        print(f"⚠️ Crypto price fetch error: {e}")
        return None

async def calculate_crypto_amount(eur_amount, crypto_type):
    """Rechne EUR-Betrag in Crypto um"""
    prices = await get_crypto_prices()
    if not prices:
        return None
    
    if crypto_type == "bitcoin":
        return eur_amount / prices['bitcoin']
    elif crypto_type == "ethereum":
        return eur_amount / prices['ethereum']
    else:
        return None

# Neue Payment Handler
async def handle_tebex_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use):
    """Handle Tebex Code Payment"""
    server_config = get_server_config(interaction.guild.id)
    tebex_domain = server_config.get("payment", {}).get("tebex_domain", "shop.example.com")
    
    embed = discord.Embed(
        title="🛒 Tebex Code Zahlung",
        description=f"**Shop:** `{tebex_domain}`\n**Betrag:** {final_price:.2f}€\n**Verwendungszweck:** `{purpose_of_use}`\n\n✅ Kaufe einen Tebex-Code im Wert von {final_price:.2f}€ und gib ihn hier ein.",
        color=0xff6b35
    )
    embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    
    # Tebex Code eingeben
    tebex_button = Button(label="🛒 Tebex Code eingeben", style=discord.ButtonStyle.primary)
    tebex_button.callback = lambda i: show_tebex_code_modal(i, ticket_channel, user, final_price, purpose_of_use)
    
    payment_view = View(timeout=None)
    payment_view.add_item(tebex_button)
    
    banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    await ticket_channel.send(embed=embed, view=payment_view, file=banner_file)
    
    await interaction.response.send_message("✅ Tebex Payment initiiert!", ephemeral=True)

class TebexCodeModal(Modal):
    def __init__(self, ticket_channel, user, final_price, purpose_of_use):
        super().__init__(title="🛒 Tebex Code eingeben")
        self.ticket_channel = ticket_channel
        self.user = user
        self.final_price = final_price
        self.purpose_of_use = purpose_of_use
        
        self.tebex_code = TextInput(
            label="Tebex Code",
            placeholder="Gib deinen gekauften Tebex Code ein...",
            required=True,
            max_length=50
        )
        self.add_item(self.tebex_code)
    
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛒 Tebex Code erhalten",
            description=f"**Code:** `{self.tebex_code.value}`\n**Betrag:** {self.final_price:.2f}€\n**Verwendungszweck:** `{self.purpose_of_use}`\n\n✅ Dein Tebex Code wurde an unser Team weitergeleitet.",
            color=0x00ff00
        )
        embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        
        payment_confirm_view = View(timeout=None)
        confirm_button = Button(label="✅ Code gesendet", style=discord.ButtonStyle.success)
        
        async def tebex_sent_callback(confirm_interaction):
            if confirm_interaction.user != self.user:
                await confirm_interaction.response.send_message("❌ Nur der Kunde kann die Zahlung bestätigen.", ephemeral=True)
                return
            await show_payment_loading(self.ticket_channel, self.user, self.final_price, "Tebex Code", confirm_interaction)
        
        confirm_button.callback = tebex_sent_callback
        payment_confirm_view.add_item(confirm_button)
        
        banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        await self.ticket_channel.send(embed=embed, view=payment_confirm_view, file=banner_file)
        await interaction.response.send_message("✅ Tebex Code übermittelt!", ephemeral=True)

async def show_tebex_code_modal(interaction, ticket_channel, user, final_price, purpose_of_use):
    modal = TebexCodeModal(ticket_channel, user, final_price, purpose_of_use)
    await interaction.response.send_modal(modal)

async def handle_amazon_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use):
    """Handle Amazon Giftcard Payment"""
    embed = discord.Embed(
        title="📦 Amazon Giftcard Zahlung",
        description=f"**Betrag:** {final_price:.2f}€\n**Verwendungszweck:** `{purpose_of_use}`\n\n✅ Sende uns einen Amazon Gutschein im Wert von {final_price:.2f}€ oder mehr.",
        color=0xff9900
    )
    embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    
    amazon_button = Button(label="📦 Amazon Gutschein senden", style=discord.ButtonStyle.primary)
    amazon_button.callback = lambda i: show_amazon_card_modal(i, ticket_channel, user, final_price, purpose_of_use)
    
    payment_view = View(timeout=None)
    payment_view.add_item(amazon_button)
    
    banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    await ticket_channel.send(embed=embed, view=payment_view, file=banner_file)
    
    await interaction.response.send_message("✅ Amazon Payment initiiert!", ephemeral=True)

class AmazonCardModal(Modal):
    def __init__(self, ticket_channel, user, final_price, purpose_of_use):
        super().__init__(title="📦 Amazon Gutschein")
        self.ticket_channel = ticket_channel
        self.user = user
        self.final_price = final_price
        self.purpose_of_use = purpose_of_use
        
        self.card_code = TextInput(
            label="Amazon Gutschein Code",
            placeholder="Gib deinen Amazon Gutschein Code ein...",
            required=True,
            max_length=50
        )
        
        self.card_value = TextInput(
            label="Gutschein Wert (in €)",
            placeholder="z.B. 25",
            required=True,
            max_length=10
        )
        
        self.add_item(self.card_code)
        self.add_item(self.card_value)
    
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📦 Amazon Gutschein erhalten",
            description=f"**Code:** `{self.card_code.value}`\n**Wert:** {self.card_value.value}€\n**Benötigt:** {self.final_price:.2f}€\n**Verwendungszweck:** `{self.purpose_of_use}`\n\n✅ Dein Amazon Gutschein wurde an unser Team weitergeleitet.",
            color=0x00ff00
        )
        embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        
        payment_confirm_view = View(timeout=None)
        confirm_button = Button(label="✅ Gutschein gesendet", style=discord.ButtonStyle.success)
        
        async def amazon_sent_callback(confirm_interaction):
            if confirm_interaction.user != self.user:
                await confirm_interaction.response.send_message("❌ Nur der Kunde kann die Zahlung bestätigen.", ephemeral=True)
                return
            await show_payment_loading(self.ticket_channel, self.user, self.final_price, "Amazon Giftcard", confirm_interaction)
        
        confirm_button.callback = amazon_sent_callback
        payment_confirm_view.add_item(confirm_button)
        
        banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        await self.ticket_channel.send(embed=embed, view=payment_confirm_view, file=banner_file)
        await interaction.response.send_message("✅ Amazon Gutschein übermittelt!", ephemeral=True)

async def show_amazon_card_modal(interaction, ticket_channel, user, final_price, purpose_of_use):
    modal = AmazonCardModal(ticket_channel, user, final_price, purpose_of_use)
    await interaction.response.send_modal(modal)

async def handle_netflix_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use):
    """Handle Netflix Card Payment"""
    embed = discord.Embed(
        title="🎬 Netflix Card Zahlung",
        description=f"**Betrag:** {final_price:.2f}€\n**Verwendungszweck:** `{purpose_of_use}`\n\n✅ Sende uns eine Netflix Karte im Wert von {final_price:.2f}€ oder mehr.",
        color=0xe50914
    )
    embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    
    netflix_button = Button(label="🎬 Netflix Karte senden", style=discord.ButtonStyle.primary)
    netflix_button.callback = lambda i: show_netflix_card_modal(i, ticket_channel, user, final_price, purpose_of_use)
    
    payment_view = View(timeout=None)
    payment_view.add_item(netflix_button)
    
    banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    await ticket_channel.send(embed=embed, view=payment_view, file=banner_file)
    
    await interaction.response.send_message("✅ Netflix Payment initiiert!", ephemeral=True)

class NetflixCardModal(Modal):
    def __init__(self, ticket_channel, user, final_price, purpose_of_use):
        super().__init__(title="🎬 Netflix Karte")
        self.ticket_channel = ticket_channel
        self.user = user
        self.final_price = final_price
        self.purpose_of_use = purpose_of_use
        
        self.card_code = TextInput(
            label="Netflix Karten Code",
            placeholder="Gib deinen Netflix Karten Code ein...",
            required=True,
            max_length=50
        )
        
        self.card_value = TextInput(
            label="Karten Wert (in €)",
            placeholder="z.B. 25",
            required=True,
            max_length=10
        )
        
        self.add_item(self.card_code)
        self.add_item(self.card_value)
    
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎬 Netflix Karte erhalten",
            description=f"**Code:** `{self.card_code.value}`\n**Wert:** {self.card_value.value}€\n**Benötigt:** {self.final_price:.2f}€\n**Verwendungszweck:** `{self.purpose_of_use}`\n\n✅ Deine Netflix Karte wurde an unser Team weitergeleitet.",
            color=0x00ff00
        )
        embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        
        payment_confirm_view = View(timeout=None)
        confirm_button = Button(label="✅ Karte gesendet", style=discord.ButtonStyle.success)
        
        async def netflix_sent_callback(confirm_interaction):
            if confirm_interaction.user != self.user:
                await confirm_interaction.response.send_message("❌ Nur der Kunde kann die Zahlung bestätigen.", ephemeral=True)
                return
            await show_payment_loading(self.ticket_channel, self.user, self.final_price, "Netflix Card", confirm_interaction)
        
        confirm_button.callback = netflix_sent_callback
        payment_confirm_view.add_item(confirm_button)
        
        banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
        await self.ticket_channel.send(embed=embed, view=payment_confirm_view, file=banner_file)
        await interaction.response.send_message("✅ Netflix Karte übermittelt!", ephemeral=True)

async def show_netflix_card_modal(interaction, ticket_channel, user, final_price, purpose_of_use):
    modal = NetflixCardModal(ticket_channel, user, final_price, purpose_of_use)
    await interaction.response.send_modal(modal)

async def handle_creditcard_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use):
    """Handle Credit Card Payment"""
    server_config = get_server_config(interaction.guild.id)
    payment_config = server_config.get("payment", {})
    cc_site = payment_config.get("creditcard_site", "payment-site.com")
    cc_number = payment_config.get("creditcard_number", "****-****-****-****")
    
    embed = discord.Embed(
        title="💳 Credit Card Zahlung",
        description=f"**Payment-Site:** `{cc_site}`\n**Karte:** `{cc_number}`\n**Betrag:** {final_price:.2f}€\n**Verwendungszweck:** `{purpose_of_use}`\n\n✅ Besuche die Payment-Site und zahle {final_price:.2f}€.",
        color=0x1f4e79
    )
    embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    
    payment_confirm_view = View(timeout=None)
    confirm_button = Button(label="✅ Zahlung gesendet", style=discord.ButtonStyle.success)
    
    async def cc_payment_sent_callback(confirm_interaction):
        if confirm_interaction.user != user:
            await confirm_interaction.response.send_message("❌ Nur der Kunde kann die Zahlung bestätigen.", ephemeral=True)
            return
        await show_payment_loading(ticket_channel, user, final_price, "Credit Card", confirm_interaction)
    
    confirm_button.callback = cc_payment_sent_callback
    payment_confirm_view.add_item(confirm_button)
    
    banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    await ticket_channel.send(embed=embed, view=payment_confirm_view, file=banner_file)
    
    await interaction.response.send_message("✅ Credit Card Details gesendet!", ephemeral=True)

async def handle_bitcoin_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use):
    """Handle Bitcoin Payment with Real-time Conversion"""
    server_config = get_server_config(interaction.guild.id)
    btc_wallet = server_config.get("payment", {}).get("crypto", {}).get("bitcoin_wallet", "bc1q...")
    
    # Real-time Bitcoin Umrechnung
    btc_amount = await calculate_crypto_amount(final_price, "bitcoin")
    crypto_prices = await get_crypto_prices()
    
    if btc_amount is None or crypto_prices is None:
        await interaction.response.send_message("❌ Fehler beim Abrufen der Bitcoin-Kurse. Versuche es später erneut.", ephemeral=True)
        return
    
    btc_price = crypto_prices['bitcoin']
    btc_change = crypto_prices['btc_change']
    change_emoji = "📈" if btc_change > 0 else "📉"
    
    embed = discord.Embed(
        title="₿ Bitcoin Zahlung",
        description=f"**Wallet:** `{btc_wallet}`\n**EUR Betrag:** {final_price:.2f}€\n**BTC Betrag:** `{btc_amount:.8f} BTC`\n**BTC Kurs:** {btc_price:.2f}€ {change_emoji} {btc_change:+.2f}%\n**Verwendungszweck:** `{purpose_of_use}`\n\n✅ Sende genau {btc_amount:.8f} BTC an die Wallet-Adresse.",
        color=0xf7931a
    )
    embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    
    payment_confirm_view = View(timeout=None)
    confirm_button = Button(label="✅ Bitcoin gesendet", style=discord.ButtonStyle.success)
    
    async def btc_payment_sent_callback(confirm_interaction):
        if confirm_interaction.user != user:
            await confirm_interaction.response.send_message("❌ Nur der Kunde kann die Zahlung bestätigen.", ephemeral=True)
            return
        await show_payment_loading(ticket_channel, user, final_price, f"Bitcoin ({btc_amount:.8f} BTC)", confirm_interaction)
    
    confirm_button.callback = btc_payment_sent_callback
    payment_confirm_view.add_item(confirm_button)
    
    banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    await ticket_channel.send(embed=embed, view=payment_confirm_view, file=banner_file)
    
    await interaction.response.send_message("✅ Bitcoin Details mit Real-time Kurs gesendet!", ephemeral=True)

async def handle_ethereum_payment(interaction, ticket_channel, user, order_data, final_price, purpose_of_use):
    """Handle Ethereum Payment with Real-time Conversion"""
    server_config = get_server_config(interaction.guild.id)
    eth_wallet = server_config.get("payment", {}).get("crypto", {}).get("ethereum_wallet", "0x...")
    
    # Real-time Ethereum Umrechnung
    eth_amount = await calculate_crypto_amount(final_price, "ethereum")
    crypto_prices = await get_crypto_prices()
    
    if eth_amount is None or crypto_prices is None:
        await interaction.response.send_message("❌ Fehler beim Abrufen der Ethereum-Kurse. Versuche es später erneut.", ephemeral=True)
        return
    
    eth_price = crypto_prices['ethereum']
    eth_change = crypto_prices['eth_change']
    change_emoji = "📈" if eth_change > 0 else "📉"
    
    embed = discord.Embed(
        title="⚡ Ethereum Zahlung",
        description=f"**Wallet:** `{eth_wallet}`\n**EUR Betrag:** {final_price:.2f}€\n**ETH Betrag:** `{eth_amount:.6f} ETH`\n**ETH Kurs:** {eth_price:.2f}€ {change_emoji} {eth_change:+.2f}%\n**Verwendungszweck:** `{purpose_of_use}`\n\n✅ Sende genau {eth_amount:.6f} ETH an die Wallet-Adresse.",
        color=0x627eea
    )
    embed.set_image(url="attachment://bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    
    payment_confirm_view = View(timeout=None)
    confirm_button = Button(label="✅ Ethereum gesendet", style=discord.ButtonStyle.success)
    
    async def eth_payment_sent_callback(confirm_interaction):
        if confirm_interaction.user != user:
            await confirm_interaction.response.send_message("❌ Nur der Kunde kann die Zahlung bestätigen.", ephemeral=True)
            return
        await show_payment_loading(ticket_channel, user, final_price, f"Ethereum ({eth_amount:.6f} ETH)", confirm_interaction)
    
    confirm_button.callback = eth_payment_sent_callback
    payment_confirm_view.add_item(confirm_button)
    
    banner_file = discord.File("attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif")
    await ticket_channel.send(embed=embed, view=payment_confirm_view, file=banner_file)
    
    await interaction.response.send_message("✅ Ethereum Details mit Real-time Kurs gesendet!", ephemeral=True)

async def show_welcome_messages_modal(interaction):
    await interaction.response.send_message("🚧 Willkommensnachrichten werden noch entwickelt...", ephemeral=True)

# Review Channel Creation Function
async def create_review_channel(interaction):
    """Automatisch Review-Channel erstellen"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    try:
        guild = interaction.guild
        
        # Check if review channel already exists
        server_config = get_server_config(guild.id)
        existing_channel_id = server_config.get("channels", {}).get("review_channel")
        
        if existing_channel_id:
            existing_channel = guild.get_channel(existing_channel_id)
            if existing_channel:
                embed = discord.Embed(
                    title="⭐ Review-Channel bereits vorhanden",
                    description=f"Es existiert bereits ein Review-Channel: {existing_channel.mention}\n\nSoll ein neuer Channel erstellt werden?",
                    color=0xffa500
                )
                
                view = View(timeout=60)
                
                # Create new button
                create_new_button = Button(label="🆕 Neuen erstellen", style=discord.ButtonStyle.danger)
                create_new_button.callback = lambda i: create_new_review_channel(i, guild)
                
                # Keep existing button
                keep_button = Button(label="✅ Bestehenden behalten", style=discord.ButtonStyle.success)
                keep_button.callback = lambda i: i.response.send_message("✅ Bestehender Review-Channel wird beibehalten.", ephemeral=True)
                
                view.add_item(create_new_button)
                view.add_item(keep_button)
                
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return
        
        # Create new review channel
        await create_new_review_channel(interaction, guild)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Fehler beim Erstellen des Review-Channels",
            description=f"Ein Fehler ist aufgetreten: {str(e)}",
            color=0xff0000
        )
        
        try:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=error_embed, ephemeral=True)

async def create_new_review_channel(interaction, guild):
    """Erstelle neuen Review-Channel"""
    try:
        # Create the review channel
        review_channel = await guild.create_text_channel(
            name="⭐-customer-reviews",
            topic="🌟 Kundenbewertungen und Feedback für unsere Services",
            reason="Automatisch erstellt durch Haze Visuals Bot"
        )
        
        # Set permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                send_messages=False,
                add_reactions=True,
                read_messages=True
            ),
            guild.me: discord.PermissionOverwrite(
                send_messages=True,
                read_messages=True,
                manage_messages=True
            )
        }
        
        # Find staff roles and give them permissions
        hv_team_role = discord.utils.get(guild.roles, name="HV | Team")
        hv_leitung_role = discord.utils.get(guild.roles, name="HV | Leitung")
        
        if hv_team_role:
            overwrites[hv_team_role] = discord.PermissionOverwrite(
                send_messages=True,
                read_messages=True,
                manage_messages=True
            )
        
        if hv_leitung_role:
            overwrites[hv_leitung_role] = discord.PermissionOverwrite(
                send_messages=True,
                read_messages=True,
                manage_messages=True
            )
        
        await review_channel.edit(overwrites=overwrites)
        
        # Save to config
        server_config = get_server_config(guild.id)
        if "channels" not in server_config:
            server_config["channels"] = {}
        server_config["channels"]["review_channel"] = review_channel.id
        save_server_config(guild.id, server_config)
        
        # Create welcome message in review channel
        welcome_embed = discord.Embed(
            title="⭐ Customer Reviews",
            description="**Willkommen im Review-Channel!**\n\nHier werden automatisch alle Kundenbewertungen gepostet, wenn Tickets abgeschlossen werden.\n\n🌟 **Features:**\n• 1-5 Sterne Bewertungssystem\n• Optionale Kommentare\n• Automatische Veröffentlichung\n• Nachvollziehbare Kundenzufriedenheit",
            color=0xffd700
        )
        welcome_embed.set_footer(text="Haze Visuals Bot • Automatisches Review-System")
        
        await review_channel.send(embed=welcome_embed)
        
        # Confirm creation
        success_embed = discord.Embed(
            title="✅ Review-Channel erfolgreich erstellt!",
            description=f"**Channel:** {review_channel.mention}\n**ID:** `{review_channel.id}`\n\n🎯 **Konfiguriert:**\n• Nur Team kann schreiben\n• Kunden können reagieren\n• Automatische Review-Veröffentlichung\n• Berechtigungen für Staff-Rollen",
            color=0x00ff00
        )
        success_embed.add_field(
            name="🔧 Nächste Schritte:",
            value="• Channel-Position anpassen\n• Weitere Berechtigungen setzen\n• Review-System testen",
            inline=False
        )
        
        try:
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=success_embed, ephemeral=True)
        
        print(f"✅ Review-Channel erstellt für {guild.name}: {review_channel.name} (ID: {review_channel.id})")
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Fehler beim Erstellen des Channels",
            description=f"Konnte Review-Channel nicht erstellen: {str(e)}",
            color=0xff0000
        )
        
        try:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=error_embed, ephemeral=True)

# Winner Channel Creation Function
async def create_winner_channel(interaction):
    """Automatisch Winner-Channel erstellen"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    try:
        guild = interaction.guild
        
        # Check if winner channel already exists
        server_config = get_server_config(guild.id)
        existing_channel_id = server_config.get("channels", {}).get("winner_channel")
        
        if existing_channel_id:
            existing_channel = guild.get_channel(existing_channel_id)
            if existing_channel:
                embed = discord.Embed(
                    title="🏆 Winner-Channel bereits vorhanden",
                    description=f"Es existiert bereits ein Winner-Channel: {existing_channel.mention}\n\nSoll ein neuer Channel erstellt werden?",
                    color=0xffa500
                )
                
                view = View(timeout=60)
                
                # Create new button
                create_new_button = Button(label="🆕 Neuen erstellen", style=discord.ButtonStyle.danger)
                create_new_button.callback = lambda i: create_new_winner_channel(i, guild)
                
                # Keep existing button
                keep_button = Button(label="✅ Bestehenden behalten", style=discord.ButtonStyle.success)
                keep_button.callback = lambda i: i.response.send_message("✅ Bestehender Winner-Channel wird beibehalten.", ephemeral=True)
                
                view.add_item(create_new_button)
                view.add_item(keep_button)
                
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return
        
        # Create new winner channel
        await create_new_winner_channel(interaction, guild)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Fehler beim Erstellen des Winner-Channels",
            description=f"Ein Fehler ist aufgetreten: {str(e)}",
            color=0xff0000
        )
        
        try:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=error_embed, ephemeral=True)

async def create_new_winner_channel(interaction, guild):
    """Erstelle neuen Winner-Channel"""
    try:
        # Create the winner channel
        winner_channel = await guild.create_text_channel(
            name="🏆-giveaway-winners",
            topic="🎉 Hier werden alle Giveaway-Gewinner verkündet",
            reason="Automatisch erstellt durch Haze Visuals Bot"
        )
        
        # Set permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                send_messages=False,
                add_reactions=True,
                read_messages=True
            ),
            guild.me: discord.PermissionOverwrite(
                send_messages=True,
                read_messages=True,
                manage_messages=True
            )
        }
        
        # Find staff roles and give them permissions
        hv_team_role = discord.utils.get(guild.roles, name="HV | Team")
        hv_leitung_role = discord.utils.get(guild.roles, name="HV | Leitung")
        
        if hv_team_role:
            overwrites[hv_team_role] = discord.PermissionOverwrite(
                send_messages=True,
                read_messages=True,
                manage_messages=True
            )
        
        if hv_leitung_role:
            overwrites[hv_leitung_role] = discord.PermissionOverwrite(
                send_messages=True,
                read_messages=True,
                manage_messages=True
            )
        
        await winner_channel.edit(overwrites=overwrites)
        
        # Save to config
        server_config = get_server_config(guild.id)
        if "channels" not in server_config:
            server_config["channels"] = {}
        server_config["channels"]["winner_channel"] = winner_channel.id
        save_server_config(guild.id, server_config)
        
        # Create welcome message in winner channel
        welcome_embed = discord.Embed(
            title="🏆 Giveaway Winners",
            description="**Willkommen im Winner-Channel!**\n\nHier werden automatisch alle Giveaway-Gewinner verkündet.\n\n🎉 **Features:**\n• Automatische Gewinner-Verkündung\n• Preis und Teilnehmerzahl\n• Zeitstempel der Gewinne\n• Gewinner-Profile",
            color=0xffd700
        )
        welcome_embed.set_footer(text="Haze Visuals Bot • Giveaway Winner System")
        
        await winner_channel.send(embed=welcome_embed)
        
        # Confirm creation
        success_embed = discord.Embed(
            title="✅ Winner-Channel erfolgreich erstellt!",
            description=f"**Channel:** {winner_channel.mention}\n**ID:** `{winner_channel.id}`\n\n🎯 **Konfiguriert:**\n• Nur Team kann schreiben\n• Mitglieder können reagieren\n• Automatische Gewinner-Verkündung\n• Berechtigungen für Staff-Rollen",
            color=0x00ff00
        )
        success_embed.add_field(
            name="🔧 Nächste Schritte:",
            value="• Channel-Position anpassen\n• Giveaway mit /giveaway erstellen\n• Automatische Verkündungen testen",
            inline=False
        )
        
        try:
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=success_embed, ephemeral=True)
        
        print(f"✅ Winner-Channel erstellt für {guild.name}: {winner_channel.name} (ID: {winner_channel.id})")
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Fehler beim Erstellen des Channels",
            description=f"Konnte Winner-Channel nicht erstellen: {str(e)}",
            color=0xff0000
        )
        
        try:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=error_embed, ephemeral=True)

async def show_ticket_messages_modal(interaction):
    await interaction.response.send_message("🚧 Ticket-Nachrichten werden noch entwickelt...", ephemeral=True)

async def show_error_messages_modal(interaction):
    await interaction.response.send_message("🚧 Fehlermeldungen werden noch entwickelt...", ephemeral=True)

async def show_language_modal(interaction):
    await interaction.response.send_message("🚧 Sprach-Einstellungen werden noch entwickelt...", ephemeral=True)

async def run_basic_setup(interaction):
    """Schneller Setup für grundlegende Bot-Konfiguration"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        
        # Setup-Fortschritt anzeigen
        progress_embed = discord.Embed(
            title="🚀 Schneller Setup läuft...",
            description="Bot wird für deinen Server konfiguriert...",
            color=0x00ff00
        )
        await interaction.followup.send(embed=progress_embed, ephemeral=True)
        
        # 1. Grundlegende Rollen erstellen
        admin_role = None
        staff_role = None
        customer_role = None
        
        existing_roles = [role.name.lower() for role in guild.roles]
        
        # Admin-Rolle
        if "admin" not in existing_roles and "administrator" not in existing_roles:
            try:
                admin_role = await guild.create_role(
                    name="Admin",
                    color=discord.Color.red(),
                    permissions=discord.Permissions.all(),
                    reason="Schneller Bot Setup - Admin Rolle"
                )
            except:
                pass
        
        # Staff-Rolle  
        if "staff" not in existing_roles and "team" not in existing_roles:
            try:
                staff_role = await guild.create_role(
                    name="Staff",
                    color=discord.Color.blue(),
                    permissions=discord.Permissions(
                        manage_messages=True,
                        manage_channels=True,
                        kick_members=True,
                        manage_roles=True
                    ),
                    reason="Schneller Bot Setup - Staff Rolle"
                )
            except:
                pass
        
        # Kunden-Rolle
        if "kunde" not in existing_roles and "customer" not in existing_roles:
            try:
                customer_role = await guild.create_role(
                    name="Kunde",
                    color=discord.Color.green(),
                    reason="Schneller Bot Setup - Kunden Rolle"
                )
            except:
                pass
        
        # 2. Ticket-Kategorien erstellen
        ticket_categories = {}
        
        # Offene Tickets Kategorie
        try:
            open_category = await guild.create_category(
                "📋 Offene Tickets",
                reason="Schneller Bot Setup - Ticket Kategorie"
            )
            ticket_categories["open"] = open_category.id
        except:
            pass
        
        # Bearbeitete Tickets Kategorie
        try:
            claimed_category = await guild.create_category(
                "🔧 Bearbeitete Tickets", 
                reason="Schneller Bot Setup - Bearbeitete Tickets"
            )
            ticket_categories["claimed"] = claimed_category.id
        except:
            pass
        
        # Bezahlte Tickets Kategorie
        try:
            paid_category = await guild.create_category(
                "💰 Bezahlte Tickets",
                reason="Schneller Bot Setup - Bezahlte Tickets"
            )
            ticket_categories["paid"] = paid_category.id
        except:
            pass
        
        # Fertige Tickets Kategorie
        try:
            finished_category = await guild.create_category(
                "✅ Fertige Tickets",
                reason="Schneller Bot Setup - Fertige Tickets"
            )
            ticket_categories["finished"] = finished_category.id
        except:
            pass
        
        # 3. Server-Konfiguration speichern
        server_config = {
            "branding": {
                "bot_name": f"{guild.name} Bot",
                "primary_color": "#0099ff",
                "footer_text": f"{guild.name} • Ticket System"
            },
            "roles": {
                "admin_role": admin_role.name if admin_role else "Admin",
                "staff_role": staff_role.name if staff_role else "Staff", 
                "customer_role": customer_role.name if customer_role else "Kunde"
            },
            "categories": ticket_categories,
            "payment": {
                "paypal_email": "ihr@paypal.email"
            },
            "pricing": {
                "Basis Paket": 15.0,
                "Premium Paket": 25.0,
                "Custom Design": 35.0
            },
            "setup_completed": True,
            "setup_date": datetime.now().isoformat()
        }
        
        save_server_config(guild.id, server_config)
        
        # 4. Ticket Counter Channel erstellen
        if ticket_categories.get("open"):
            try:
                counter_category = guild.get_channel(ticket_categories["open"])
                await counter_category.create_voice_channel(
                    "📊 Offene Tickets: 0",
                    reason="Schneller Bot Setup - Ticket Counter"
                )
            except:
                pass
        
        # 5. Erfolgsmeldung
        success_embed = discord.Embed(
            title="✅ Schneller Setup abgeschlossen!",
            description="Dein Bot wurde erfolgreich konfiguriert:",
            color=0x00ff00
        )
        
        setup_info = ""
        if admin_role:
            setup_info += f"👑 **Admin-Rolle:** {admin_role.mention}\n"
        if staff_role:
            setup_info += f"🛠️ **Staff-Rolle:** {staff_role.mention}\n"
        if customer_role:
            setup_info += f"👤 **Kunden-Rolle:** {customer_role.mention}\n"
        
        setup_info += f"\n📋 **Ticket-Kategorien:** {len(ticket_categories)} erstellt\n"
        setup_info += f"🤖 **Bot-Name:** {guild.name} Bot\n"
        setup_info += f"💳 **Beispiel-Preise:** 3 Pakete konfiguriert"
        
        success_embed.add_field(
            name="🎯 Was wurde eingerichtet:",
            value=setup_info,
            inline=False
        )
        
        success_embed.add_field(
            name="⚡ Nächste Schritte:",
            value="• Verwende `/ticket_panel` um das Ticket-System zu aktivieren\n• Nutze `/admin` um weitere Anpassungen vorzunehmen\n• Konfiguriere deine PayPal-Email in den Zahlungseinstellungen",
            inline=False
        )
        
        success_embed.set_footer(text=f"{guild.name} • Setup erfolgreich")
        
        await interaction.followup.edit_message(
            message_id=(await interaction.original_response()).id,
            embed=success_embed
        )
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Setup Fehler",
            description=f"Es gab einen Fehler beim Setup: {str(e)}\n\nBitte stelle sicher, dass der Bot die nötigen Berechtigungen hat.",
            color=0xff0000
        )
        await interaction.followup.edit_message(
            message_id=(await interaction.original_response()).id,
            embed=error_embed
        )

async def run_gaming_setup(interaction):
    """Vollständiger Gaming Setup mit allen Channels und Features"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        
        # Setup-Fortschritt anzeigen
        progress_embed = discord.Embed(
            title="🎮 Gaming Setup läuft...",
            description="Erstelle Gaming-Community mit allen Features...",
            color=0xff6b35
        )
        await interaction.followup.send(embed=progress_embed, ephemeral=True)
        
        # 1. Gaming Rollen erstellen
        admin_role = await guild.create_role(
            name="👑 Server Owner",
            color=discord.Color.gold(),
            permissions=discord.Permissions.all(),
            reason="Gaming Setup - Owner"
        )
        
        mod_role = await guild.create_role(
            name="🛡️ Moderator", 
            color=discord.Color.red(),
            permissions=discord.Permissions(
                manage_messages=True,
                manage_channels=True,
                kick_members=True,
                ban_members=True,
                manage_roles=True
            ),
            reason="Gaming Setup - Moderator"
        )
        
        vip_role = await guild.create_role(
            name="⭐ VIP Player",
            color=discord.Color.purple(),
            permissions=discord.Permissions(
                connect=True,
                speak=True,
                stream=True
            ),
            reason="Gaming Setup - VIP"
        )
        
        gamer_role = await guild.create_role(
            name="🎮 Gamer",
            color=discord.Color.blue(),
            reason="Gaming Setup - Gamer"
        )
        
        # 2. Gaming Kategorien erstellen
        # Support System
        ticket_open = await guild.create_category("🎫 Player Support")
        ticket_claimed = await guild.create_category("🔧 In Progress") 
        ticket_paid = await guild.create_category("💎 VIP Services")
        ticket_finished = await guild.create_category("✅ Solved")
        
        # Gaming Bereiche
        main_area = await guild.create_category("🏠 Main Hub")
        gaming_category = await guild.create_category("🎮 Gaming Lounge")
        events_category = await guild.create_category("🎉 Events & Tournaments")
        shop_category = await guild.create_category("🛒 Game Shop")
        
        # 3. Main Hub Channels
        welcome_channel = await main_area.create_text_channel(
            "👋-welcome",
            topic="Welcome to our Gaming Community! 🎮"
        )
        rules_channel = await main_area.create_text_channel(
            "📜-server-rules",
            topic="Community Rules & Guidelines"
        )
        announcements_channel = await main_area.create_text_channel(
            "📢-announcements",
            topic="Important Server Announcements"
        )
        general_chat = await main_area.create_text_channel(
            "💬-general-chat",
            topic="General Gaming Discussion"
        )
        
        # 4. Gaming Lounge
        game_chat = await gaming_category.create_text_channel(
            "🎯-game-chat",
            topic="Chat about your favorite games!"
        )
        lfg_channel = await gaming_category.create_text_channel(
            "👥-looking-for-group",
            topic="Find teammates and gaming partners"
        )
        screenshots_channel = await gaming_category.create_text_channel(
            "📸-screenshots-clips",
            topic="Share your epic gaming moments!"
        )
        
        # Voice Channels für Gaming
        await gaming_category.create_voice_channel("🎮 Gaming Lounge 1")
        await gaming_category.create_voice_channel("🎮 Gaming Lounge 2")
        await gaming_category.create_voice_channel("⭐ VIP Gaming Room")
        
        # 5. Events & Tournaments
        events_channel = await events_category.create_text_channel(
            "🎉-events-info",
            topic="Upcoming Gaming Events & Tournaments"
        )
        tournament_channel = await events_category.create_text_channel(
            "🏆-tournaments",
            topic="Tournament Registration & Results"
        )
        await events_category.create_voice_channel("🎤 Event Stage")
        
        # 6. Game Shop
        shop_channel = await shop_category.create_text_channel(
            "🛒-game-services",
            topic="Order Gaming Services & Coaching"
        )
        pricing_channel = await shop_category.create_text_channel(
            "💰-prices-packages",
            topic="Gaming Service Prices & Packages"
        )
        support_channel = await shop_category.create_text_channel(
            "🎧-support-tickets",
            topic="Create support tickets for services"
        )
        
        # Counter Channel
        await ticket_open.create_voice_channel("📊 Open Tickets: 0")
        
        # 7. Server-Konfiguration speichern
        server_config = {
            "branding": {
                "bot_name": f"{guild.name} Gaming Bot",
                "primary_color": "#ff6b35", 
                "footer_text": f"{guild.name} • Gaming Community"
            },
            "roles": {
                "admin_role": admin_role.name,
                "staff_role": mod_role.name,
                "vip_role": vip_role.name,
                "customer_role": gamer_role.name
            },
            "categories": {
                "open": ticket_open.id,
                "claimed": ticket_claimed.id,
                "paid": ticket_paid.id,
                "finished": ticket_finished.id
            },
            "channels": {
                "welcome": welcome_channel.id,
                "rules": rules_channel.id,
                "general": general_chat.id,
                "lfg": lfg_channel.id,
                "shop": shop_channel.id,
                "support": support_channel.id,
                "events": events_channel.id
            },
            "payment": {
                "paypal_email": "gaming@yourserver.com"
            },
            "pricing": {
                "Game Coaching": 25.0,
                "Boost Service": 45.0,
                "VIP Access": 15.0,
                "Tournament Entry": 10.0,
                "Custom Service": 50.0
            },
            "setup_type": "gaming",
            "setup_completed": True,
            "setup_date": datetime.now().isoformat()
        }
        
        save_server_config(guild.id, server_config)
        
        # 8. Panels automatisch erstellen
        
        # Gaming Services Panel
        shop_embed = discord.Embed(
            title="🛒 Gaming Services Shop",
            description="Level up your gaming experience!",
            color=0xff6b35
        )
        shop_embed.add_field(
            name="🎯 Available Services:",
            value="🎮 **Game Coaching** - Improve your skills\n🚀 **Boost Services** - Rank up faster\n⭐ **VIP Access** - Exclusive perks\n🏆 **Tournament Entry** - Join competitions\n💎 **Custom Services** - Special requests",
            inline=False
        )
        
        ticket_view = TicketPanelView()
        await support_channel.send(embed=shop_embed, view=ticket_view)
        
        # Pricing Panel
        pricing_embed = discord.Embed(
            title="💰 Gaming Service Prices",
            description="Affordable gaming services for everyone!",
            color=0xff6b35
        )
        pricing_embed.add_field(
            name="🎮 Game Coaching - 25€",
            value="• 2 hours personal coaching\n• Strategy guides\n• Skill improvement\n• Tips & tricks",
            inline=True
        )
        pricing_embed.add_field(
            name="🚀 Boost Service - 45€",
            value="• Rank/Level boosting\n• Achievement unlocks\n• Progress acceleration\n• Safe & reliable",
            inline=True
        )
        pricing_embed.add_field(
            name="⭐ VIP Access - 15€/month",
            value="• Exclusive channels\n• Priority support\n• Special events\n• Custom role",
            inline=True
        )
        
        await pricing_channel.send(embed=pricing_embed)
        
        # Welcome Message mit Gaming Theme
        welcome_embed = discord.Embed(
            title=f"🎮 Welcome to {guild.name}!",
            description="Your ultimate gaming community awaits!",
            color=0xff6b35
        )
        welcome_embed.add_field(
            name="🎯 What we offer:",
            value="• Gaming Services & Coaching\n• Community Events\n• Tournament Participation\n• VIP Gaming Experience",
            inline=True
        )
        welcome_embed.add_field(
            name="🚀 Get started:",
            value="• Check <#" + str(rules_channel.id) + "> first\n• Browse services in <#" + str(shop_channel.id) + ">\n• Join the gaming chat in <#" + str(game_chat.id) + ">",
            inline=True
        )
        welcome_embed.set_footer(text="Ready Player One? 🎮")
        
        await welcome_channel.send(embed=welcome_embed)
        
        # Server Rules
        rules_embed = discord.Embed(
            title="📜 Gaming Community Rules",
            description="Keep our community fun and fair for everyone!",
            color=0xff6b35
        )
        rules_embed.add_field(
            name="🎮 Gaming Rules:",
            value="1️⃣ No cheating or hacking\n2️⃣ Be respectful to all players\n3️⃣ No spam in voice/text channels\n4️⃣ Use appropriate channels\n5️⃣ Have fun and game on! 🎉",
            inline=False
        )
        
        await rules_channel.send(embed=rules_embed)
        
        # 9. Erfolgsmeldung
        success_embed = discord.Embed(
            title="✅ Gaming Setup abgeschlossen!",
            description="Deine Gaming-Community ist bereit zum Spielen:",
            color=0x00ff00
        )
        
        setup_info = f"""
🎮 **4 Gaming Rollen** erstellt
📁 **8 Kategorien** mit 15+ Channels  
🛒 **Game Shop** mit Services aktiv
🎫 **Support-System** eingerichtet
🏆 **Tournament-Bereich** bereit
💬 **Gaming-Chat** & Voice-Channels
⭐ **VIP-System** aktiviert
📜 **Community-Regeln** gesetzt
        """
        
        success_embed.add_field(
            name="🎯 Was wurde eingerichtet:",
            value=setup_info.strip(),
            inline=False
        )
        
        success_embed.add_field(
            name="🚀 Sofort verfügbar:",
            value="• Spieler können Services bestellen\n• Community-Chat aktiv\n• Events planbar\n• VIP-System funktional",
            inline=False
        )
        
        await interaction.followup.edit_message(
            message_id=(await interaction.original_response()).id,
            embed=success_embed
        )
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Gaming Setup Fehler", 
            description=f"Fehler beim Setup: {str(e)}",
            color=0xff0000
        )
        await interaction.followup.edit_message(
            message_id=(await interaction.original_response()).id,
            embed=error_embed
        )

async def run_business_setup(interaction):
    """Vollständiger Business Setup mit allen Channels und Panels"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        
        # Setup-Fortschritt anzeigen
        progress_embed = discord.Embed(
            title="🏢 Business Setup läuft...",
            description="Erstelle vollständige Business-Infrastruktur...",
            color=0x0066cc
        )
        await interaction.followup.send(embed=progress_embed, ephemeral=True)
        
        # 1. Business Rollen erstellen
        admin_role = await guild.create_role(
            name="🏢 Business Admin",
            color=discord.Color.gold(),
            permissions=discord.Permissions.all(),
            reason="Business Setup - Admin"
        )
        
        manager_role = await guild.create_role(
            name="👔 Manager",
            color=discord.Color.blue(),
            permissions=discord.Permissions(
                manage_channels=True,
                manage_messages=True,
                manage_roles=True,
                kick_members=True
            ),
            reason="Business Setup - Manager"
        )
        
        support_role = await guild.create_role(
            name="🎧 Support Team",
            color=discord.Color.green(),
            permissions=discord.Permissions(
                manage_messages=True,
                manage_channels=True
            ),
            reason="Business Setup - Support"
        )
        
        client_role = await guild.create_role(
            name="💼 Business Client",
            color=discord.Color.purple(),
            reason="Business Setup - Client"
        )
        
        # 2. Business Kategorien erstellen
        # Ticket System
        ticket_open = await guild.create_category("📋 Offene Anfragen")
        ticket_claimed = await guild.create_category("🔧 In Bearbeitung") 
        ticket_paid = await guild.create_category("💰 Bezahlt & Geplant")
        ticket_finished = await guild.create_category("✅ Abgeschlossen")
        
        # Business Bereiche
        management_category = await guild.create_category("🏢 Management")
        client_area = await guild.create_category("💼 Client Area")
        support_category = await guild.create_category("🎧 Support Center")
        
        # 3. Management Channels
        await management_category.create_text_channel(
            "📊-dashboard",
            topic="Management Dashboard & Übersicht"
        )
        await management_category.create_text_channel(
            "📈-analytics", 
            topic="Business Analytics & Reports"
        )
        await management_category.create_text_channel(
            "💬-team-chat",
            topic="Interner Team Chat"
        )
        await management_category.create_voice_channel("🎤 Team Meeting")
        
        # 4. Client Area Channels
        welcome_channel = await client_area.create_text_channel(
            "👋-willkommen",
            topic="Willkommen bei unserem Business Service!"
        )
        pricing_channel = await client_area.create_text_channel(
            "💰-preise-packages",
            topic="Unsere Service-Packages und Preise"
        )
        testimonials_channel = await client_area.create_text_channel(
            "⭐-kundenbewertungen",
            topic="Bewertungen zufriedener Kunden"
        )
        
        # 5. Support Center
        tickets_channel = await support_category.create_text_channel(
            "🎫-tickets-erstellen",
            topic="Hier können Kunden Support-Tickets erstellen"
        )
        faq_channel = await support_category.create_text_channel(
            "❓-faq-hilfe",
            topic="Häufig gestellte Fragen & Hilfe"
        )
        await support_category.create_voice_channel("🎧 Support Call")
        
        # 6. Spezial Channels
        calendar_channel = await client_area.create_text_channel(
            "📅-terminkalender",
            topic="Verfügbare Termine und Buchungen"
        )
        
        # Counter Channel
        await ticket_open.create_voice_channel("📊 Offene Anfragen: 0")
        
        # 7. Server-Konfiguration speichern
        server_config = {
            "branding": {
                "bot_name": f"{guild.name} Business Bot",
                "primary_color": "#0066cc",
                "footer_text": f"{guild.name} • Professional Business Services"
            },
            "roles": {
                "admin_role": admin_role.name,
                "staff_role": manager_role.name,
                "support_role": support_role.name,
                "customer_role": client_role.name
            },
            "categories": {
                "open": ticket_open.id,
                "claimed": ticket_claimed.id,
                "paid": ticket_paid.id,
                "finished": ticket_finished.id
            },
            "channels": {
                "welcome": welcome_channel.id,
                "pricing": pricing_channel.id,
                "tickets": tickets_channel.id,
                "calendar": calendar_channel.id,
                "testimonials": testimonials_channel.id
            },
            "payment": {
                "paypal_email": "business@yourcompany.com"
            },
            "pricing": {
                "Basic Consulting": 150.0,
                "Business Package": 350.0,
                "Premium Enterprise": 750.0,
                "Custom Solution": 1200.0
            },
            "setup_type": "business",
            "setup_completed": True,
            "setup_date": datetime.now().isoformat()
        }
        
        save_server_config(guild.id, server_config)
        
        # 8. Panels automatisch erstellen
        
        # Ticket Panel
        ticket_embed = discord.Embed(
            title="🎫 Business Support System",
            description="Wählen Sie den passenden Service-Bereich:",
            color=0x0066cc
        )
        ticket_embed.add_field(
            name="📋 Verfügbare Services:",
            value="🏢 **Business Consulting**\n💼 **Enterprise Solutions**\n🎧 **Technical Support**\n📈 **Custom Projects**\n💬 **General Inquiry**",
            inline=False
        )
        
        ticket_view = TicketPanelView()
        await tickets_channel.send(embed=ticket_embed, view=ticket_view)
        
        # Pricing Panel
        pricing_embed = discord.Embed(
            title="💰 Business Service Packages",
            description="Professionelle Lösungen für Ihr Unternehmen",
            color=0x0066cc
        )
        pricing_embed.add_field(
            name="📊 Basic Consulting - 150€",
            value="• 2 Stunden Beratung\n• Basis-Analyse\n• Empfehlungen\n• Email Support",
            inline=True
        )
        pricing_embed.add_field(
            name="💼 Business Package - 350€", 
            value="• 5 Stunden Consulting\n• Detaillierte Analyse\n• Implementierungsplan\n• 2 Wochen Support",
            inline=True
        )
        pricing_embed.add_field(
            name="🏆 Premium Enterprise - 750€",
            value="• 10 Stunden Consulting\n• Vollständige Lösung\n• Team Training\n• 1 Monat Support",
            inline=True
        )
        
        await pricing_channel.send(embed=pricing_embed)
        
        # Welcome Message
        welcome_embed = discord.Embed(
            title=f"👋 Willkommen bei {guild.name}!",
            description="Ihr Partner für professionelle Business-Lösungen",
            color=0x0066cc
        )
        welcome_embed.add_field(
            name="🎯 Unsere Services:",
            value="• Business Consulting\n• Enterprise Solutions\n• Technical Support\n• Custom Development",
            inline=True
        )
        welcome_embed.add_field(
            name="📞 So erreichen Sie uns:",
            value="• Ticket erstellen in <#" + str(tickets_channel.id) + ">\n• Preise ansehen in <#" + str(pricing_channel.id) + ">\n• Termine buchen nach Zahlung",
            inline=True
        )
        
        await welcome_channel.send(embed=welcome_embed)
        
        # Calendar Display
        await update_calendar_display()
        
        # 9. Erfolgsmeldung
        success_embed = discord.Embed(
            title="✅ Business Setup komplett!",
            description="Ihr professionelles Business-System ist einsatzbereit:",
            color=0x00ff00
        )
        
        setup_info = f"""
👥 **4 Business Rollen** erstellt
📁 **8 Kategorien** mit 12 Channels
🎫 **Ticket-System** mit Panel aktiviert
💰 **Pricing-Display** konfiguriert  
📅 **Terminkalender** eingerichtet
👋 **Welcome-System** aktiv
🏢 **Management Dashboard** bereit
        """
        
        success_embed.add_field(
            name="🎯 Was wurde eingerichtet:",
            value=setup_info.strip(),
            inline=False
        )
        
        success_embed.add_field(
            name="⚡ Sofort verfügbar:",
            value="• Kunden können Tickets erstellen\n• Preise sind sichtbar\n• Termine buchbar nach Zahlung\n• Management-Tools aktiv",
            inline=False
        )
        
        await interaction.followup.edit_message(
            message_id=(await interaction.original_response()).id,
            embed=success_embed
        )
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Business Setup Fehler",
            description=f"Fehler beim Setup: {str(e)}",
            color=0xff0000
        )
        await interaction.followup.edit_message(
            message_id=(await interaction.original_response()).id,
            embed=error_embed
        )

async def run_community_setup(interaction):
    await interaction.response.send_message("🚧 Community Setup wird noch entwickelt...", ephemeral=True)

# ========================================
# SHOP TICKET SYSTEM
# ========================================

async def create_shop_ticket(interaction: discord.Interaction):
    """Erstelle Shop-Ticket mit Kategorie-Auswahl"""
    print(f"🛍️ Shop-Ticket von {interaction.user} angefordert")
    
    # Lade Shop-Kategorien
    shop_categories = load_shop_categories()
    
    if not shop_categories:
        await interaction.response.send_message(
            "❌ **Shop nicht verfügbar**\n\n"
            "Es sind keine Shop-Kategorien konfiguriert. "
            "Bitte kontaktiere einen Administrator.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="🛍️ Shop - Kategorie auswählen",
        description="""
╔═══════════════════════════════════════╗
║              🌪️ HAZE VISUALS 🌪️              ║
║               🛍️ Shop System 🛍️               ║
╚═══════════════════════════════════════╝

**Wähle eine Produktkategorie:**
        """,
        color=0x9b59b6
    )
    
    # Dynamische Kategorie-Beschreibung
    category_descriptions = ""
    for category_name, category_data in shop_categories.items():
        description = category_data.get("description", "Keine Beschreibung")
        category_descriptions += f"\n📂 **{category_name}** - {description}"
    
    embed.description += category_descriptions + "\n\nKlicke auf eine Kategorie, um die verfügbaren Produkte zu sehen."
    embed.set_footer(text="Haze Visuals • Shop System")
    
    # Dynamische Kategorie-Auswahl-Buttons
    shop_view = View(timeout=300)
    
    category_emojis = {"Soundpacks": "🎵", "Templates/Blender": "🎨", "Discord Bots": "🤖"}
    button_styles = [discord.ButtonStyle.primary, discord.ButtonStyle.success, discord.ButtonStyle.secondary, discord.ButtonStyle.blurple, discord.ButtonStyle.danger]
    
    for i, (category_name, category_data) in enumerate(shop_categories.items()):
        emoji = category_emojis.get(category_name, "📦")
        style = button_styles[i % len(button_styles)]
        
        button = Button(
            label=f"{emoji} {category_name}",
            style=style
        )
        button.callback = lambda i, cat=category_name: show_dynamic_category(i, cat)
        shop_view.add_item(button)
    
    await interaction.response.send_message(embed=embed, view=shop_view, ephemeral=True)

async def show_dynamic_category(interaction, category_name):
    """Zeige dynamische Kategorie mit Produkten aus JSON"""
    shop_categories = load_shop_categories()
    
    if category_name not in shop_categories:
        await interaction.response.send_message(
            f"❌ Kategorie '{category_name}' nicht gefunden.",
            ephemeral=True
        )
        return
    
    category_data = shop_categories[category_name]
    products = category_data.get("products", {})
    color_hex = category_data.get("color", "#9b59b6")
    
    # Konvertiere Hex zu Discord Color
    try:
        color_int = int(color_hex.replace("#", ""), 16)
    except:
        color_int = 0x9b59b6
    
    embed = discord.Embed(
        title=f"📂 {category_name}",
        description=f"**{category_data.get('description', 'Keine Beschreibung')}**\n\n**Verfügbare Produkte:**",
        color=color_int
    )
    
    view = View(timeout=300)
    
    if not products:
        embed.add_field(
            name="❌ Keine Produkte",
            value="In dieser Kategorie sind derzeit keine Produkte verfügbar.",
            inline=False
        )
    else:
        # Zeige alle Produkte
        for product_name, product_data in products.items():
            price = product_data.get("price", "Preis auf Anfrage")
            description = product_data.get("description", "Keine Beschreibung")
            
            embed.add_field(
                name=f"🎯 {product_name}",
                value=f"{description}\n💰 **Preis:** {price}",
                inline=False
            )
            
            # Bestell-Button für jedes Produkt
            order_button = Button(
                label=f"🛒 {product_name} bestellen",
                style=discord.ButtonStyle.success
            )
            order_button.callback = lambda i, cat=category_name, prod=product_name, p=price: create_product_ticket(i, cat, prod, p)
            view.add_item(order_button)
    
    # Zurück Button
    back_button = Button(label="⬅️ Zurück zur Kategorie-Auswahl", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: create_shop_ticket(i)
    view.add_item(back_button)
    
    await interaction.response.edit_message(embed=embed, view=view)


async def create_product_ticket(interaction, category, product_name, price):
    """Erstelle Ticket für spezifisches Produkt"""
    user = interaction.user
    guild = interaction.guild
    
    # Server-Konfiguration laden
    server_config = get_server_config(guild.id)
    category_id = server_config["ticket_categories"]["tickets"]
    
    # Ticket-Name erstellen
    timestamp = int(interaction.created_at.timestamp())
    channel_name = f"shop-{user.name.lower()}-{timestamp}"
    
    # Prüfe ob User bereits ein offenes Shop-Ticket hat
    existing_shop_tickets = [
        channel for channel in guild.channels 
        if isinstance(channel, discord.TextChannel) 
        and channel.name.startswith(f"shop-{user.name.lower()}")
    ]
    
    if existing_shop_tickets:
        await interaction.response.send_message(
            f"❌ Du hast bereits ein offenes Shop-Ticket: {existing_shop_tickets[0].mention}\n"
            "Bitte schließe es zuerst, bevor du ein neues erstellst.",
            ephemeral=True
        )
        return
    
    # Kategorie finden
    ticket_category = guild.get_channel(category_id)
    if not ticket_category:
        await interaction.response.send_message("❌ Ticket-Kategorie nicht gefunden.", ephemeral=True)
        return
    
    # Sofort antworten
    await interaction.response.send_message(
        f"🔄 Erstelle dein Shop-Ticket für **{product_name}**...", 
        ephemeral=True
    )
    
    # Berechtigungen für den Ticket-Kanal
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
    }
    
    # Staff-Rollen hinzufügen
    staff_role_names = [
        server_config["roles"]["admin_role"],
        server_config["roles"]["staff_role"],
        "HV | Team",
        "HV | Leitung"
    ]
    
    for role_name in staff_role_names:
        if role_name:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
    
    try:
        # Shop-Ticket-Kanal erstellen
        ticket_channel = await guild.create_text_channel(
            channel_name,
            category=ticket_category,
            overwrites=overwrites
        )
        
        # Shop-Ticket-Embed
        embed = discord.Embed(
            title="🛍️ Shop-Bestellung",
            description=f"""
**Neue Shop-Bestellung von {user.mention}**

📦 **Kategorie:** {category}
🎯 **Produkt:** {product_name}
💰 **Preis:** {price}
🕐 **Bestellt:** <t:{int(interaction.created_at.timestamp())}:F>

✅ **Nächste Schritte:**
1. Unser Team prüft deine Bestellung
2. Du erhältst Zahlungsdetails
3. Nach Zahlungseingang beginnen wir mit der Arbeit

📞 Bei Fragen kannst du hier direkt antworten!

🎟️ **Discount-Code:** Verwende den Button unten, falls du einen Rabattcode hast.
            """,
            color=0x9b59b6
        )
        
        embed.set_footer(text="Haze Visuals • Shop System")
        
        # Ticket-Management-Buttons für Staff und Customer
        ticket_view = View(timeout=None)
        
        # Customer Button für Discount-Code (erste Reihe)
        discount_button = Button(label="🎟️ Discount-Code eingeben", style=discord.ButtonStyle.secondary, row=0)
        
        # Staff Buttons (zweite Reihe)
        claim_button = Button(label="🏷️ Claim", style=discord.ButtonStyle.success, row=1)
        paid_button = Button(label="💰 Paid", style=discord.ButtonStyle.primary, row=1)
        finished_button = Button(label="✅ Finished", style=discord.ButtonStyle.success, row=1)
        close_button = Button(label="🔒 Close", style=discord.ButtonStyle.danger, row=1)
        
        # Button-Callbacks
        async def discount_callback(discount_interaction):
            # Nur der Kunde kann Discount-Codes eingeben
            if discount_interaction.user.id != user.id:
                await discount_interaction.response.send_message("❌ Nur der Kunde kann Discount-Codes eingeben.", ephemeral=True)
                return
            
            modal = ShopDiscountCodeModal(category, product_name, price, ticket_channel, user)
            await discount_interaction.response.send_modal(modal)
        
        async def shop_claim_callback(claim_interaction):
            staff_role = discord.utils.get(claim_interaction.guild.roles, name="HV | Team")
            if staff_role not in claim_interaction.user.roles and not claim_interaction.user.guild_permissions.administrator:
                await claim_interaction.response.send_message("❌ Nur HV | Team kann Tickets claimen.", ephemeral=True)
                return
            
            await claim_interaction.response.send_message(
                f"✅ **Shop-Ticket übernommen!**\n"
                f"👤 **Bearbeiter:** {claim_interaction.user.mention}\n"
                f"📦 **Produkt:** {product_name}\n"
                f"💰 **Preis:** {price}"
            )
            print(f"🏷️ Shop-Ticket {channel_name} wurde von {claim_interaction.user} geclaimed")
        
        async def shop_paid_callback(paid_interaction):
            staff_role = discord.utils.get(paid_interaction.guild.roles, name="HV | Team")
            if staff_role not in paid_interaction.user.roles and not paid_interaction.user.guild_permissions.administrator:
                await paid_interaction.response.send_message("❌ Nur HV | Team kann Zahlungen bestätigen.", ephemeral=True)
                return
            
            # Customer-Rolle zuweisen
            try:
                customer_role = discord.utils.get(guild.roles, name=server_config["roles"]["customer_role"])
                if customer_role:
                    await user.add_roles(customer_role)
                    print(f"✅ Customer role assigned to {user}")
            except Exception as e:
                print(f"⚠️ Error assigning Customer role: {e}")
            
            await paid_interaction.response.send_message(
                f"💰 **Zahlung bestätigt!**\n"
                f"👤 **Kunde:** {user.mention}\n"
                f"📦 **Produkt:** {product_name}\n"
                f"✅ **Status:** Bezahlt - Arbeit kann beginnen!\n\n"
                f"🎉 {user.mention}, deine Zahlung wurde bestätigt! Wir beginnen nun mit der Arbeit an deinem **{product_name}**."
            )
            print(f"💰 Shop-Ticket {channel_name} als bezahlt markiert")
        
        async def shop_finished_callback(finished_interaction):
            staff_role = discord.utils.get(finished_interaction.guild.roles, name="HV | Team")
            if staff_role not in finished_interaction.user.roles and not finished_interaction.user.guild_permissions.administrator:
                await finished_interaction.response.send_message("❌ Nur HV | Team kann Tickets als fertig markieren.", ephemeral=True)
                return
            
            await finished_interaction.response.send_message(
                f"✅ **Projekt abgeschlossen!**\n"
                f"📦 **Produkt:** {product_name}\n"
                f"👤 **Kunde:** {user.mention}\n\n"
                f"🎉 {user.mention}, dein **{product_name}** ist fertig! Bitte prüfe das Ergebnis.\n\n"
                f"⭐ **Bewertung:** Falls du zufrieden bist, würden wir uns über eine Bewertung freuen!"
            )
            
            # Review-System starten
            await start_review_system(ticket_channel, user)
            print(f"✅ Shop-Ticket {channel_name} als fertig markiert")
        
        async def shop_close_callback(close_interaction):
            staff_role = discord.utils.get(close_interaction.guild.roles, name="HV | Team")
            if staff_role not in close_interaction.user.roles and not close_interaction.user.guild_permissions.administrator:
                await close_interaction.response.send_message("❌ Nur HV | Team kann Tickets schließen.", ephemeral=True)
                return
            
            await close_interaction.response.send_message(
                f"🔒 **Ticket wird geschlossen...**\n"
                f"📦 **Produkt:** {product_name}\n"
                f"👤 **Geschlossen von:** {close_interaction.user.mention}"
            )
            
            # Channel löschen nach 10 Sekunden
            await asyncio.sleep(10)
            await ticket_channel.delete()
            print(f"🔒 Shop-Ticket {channel_name} geschlossen")
        
        # Callbacks zuweisen
        discount_button.callback = discount_callback
        claim_button.callback = shop_claim_callback
        paid_button.callback = shop_paid_callback  
        finished_button.callback = shop_finished_callback
        close_button.callback = shop_close_callback
        
        # Buttons hinzufügen
        ticket_view.add_item(discount_button)  # Erste Reihe für Customer
        ticket_view.add_item(claim_button)     # Zweite Reihe für Staff
        ticket_view.add_item(paid_button)
        ticket_view.add_item(finished_button)
        ticket_view.add_item(close_button)
        
        # Ticket-Nachricht senden
        await ticket_channel.send(embed=embed, view=ticket_view)
        
        # Ticket zu pending_tickets.json hinzufügen
        try:
            with open('pending_tickets.json', 'r') as f:
                pending_tickets = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pending_tickets = {}
        
        pending_tickets[str(ticket_channel.id)] = {
            "user_id": user.id,
            "username": user.name,
            "type": "Shop",
            "category": category,
            "product": product_name,
            "price": price,
            "created_at": int(interaction.created_at.timestamp()),
            "status": "Created"
        }
        
        with open('pending_tickets.json', 'w') as f:
            json.dump(pending_tickets, f, indent=2)
        
        print(f"🛍️ Shop-Ticket erstellt: {channel_name} für {product_name} ({price})")
        
        # Ticket-Counter aktualisieren
        await update_ticket_counter(guild)
        
    except Exception as e:
        print(f"❌ Fehler beim Erstellen des Shop-Tickets: {e}")
        await interaction.followup.send(
            "❌ Es gab einen Fehler beim Erstellen des Shop-Tickets. Bitte kontaktiere einen Administrator.",
            ephemeral=True
        )

# ========================================
# ENHANCED ADMIN FEATURES & STATISTICS  
# ========================================

async def show_bot_statistics(interaction):
    """Zeige umfassende Bot-Statistiken"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    guild = interaction.guild
    
    # Server-Statistiken sammeln
    total_members = guild.member_count
    text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
    voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
    roles_count = len(guild.roles)
    
    # Bot-spezifische Statistiken
    try:
        with open('pending_tickets.json', 'r', encoding='utf-8') as f:
            pending_tickets = json.load(f)
        active_tickets = len(pending_tickets)
    except:
        active_tickets = 0
    
    try:
        with open('discount_codes.json', 'r', encoding='utf-8') as f:
            discount_codes = json.load(f)
        total_discounts = len(discount_codes)
    except:
        total_discounts = 0
    
    try:
        with open('prices.json', 'r', encoding='utf-8') as f:
            prices = json.load(f)
        total_categories = len(prices)
        total_products = sum(len(items) if isinstance(items, dict) else 0 for items in prices.values())
    except:
        total_categories = 0
        total_products = 0
    
    embed = discord.Embed(
        title="📊 Bot-Statistiken & Server-Übersicht",
        description=f"Umfassende Statistiken für **{guild.name}**",
        color=0x2ecc71
    )
    
    # Server-Info
    embed.add_field(
        name="🏠 Server-Information",
        value=f"👥 **Mitglieder:** {total_members}\n"
              f"💬 **Text-Kanäle:** {text_channels}\n"
              f"🔊 **Voice-Kanäle:** {voice_channels}\n"
              f"🎭 **Rollen:** {roles_count}",
        inline=True
    )
    
    # Bot-Funktionen
    embed.add_field(
        name="🤖 Bot-Funktionen",
        value=f"🎫 **Aktive Tickets:** {active_tickets}\n"
              f"🎟️ **Discount-Codes:** {total_discounts}\n"
              f"📁 **Kategorien:** {total_categories}\n"
              f"📦 **Produkte:** {total_products}",
        inline=True
    )
    
    # Performance-Info
    try:
        import psutil
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent()
        
        embed.add_field(
            name="⚙️ Performance",
            value=f"💾 **RAM:** {memory.percent}%\n"
                  f"⚡ **CPU:** {cpu_percent}%\n"
                  f"🚀 **Status:** Online\n"
                  f"📊 **Health:** Optimal",
            inline=True
        )
    except:
        embed.add_field(
            name="⚙️ Performance",
            value="📊 **Status:** Online\n🚀 **Health:** Optimal",
            inline=True
        )
    
    embed.set_footer(text=f"Statistiken • {datetime.datetime.now().strftime('%d.%m.%Y um %H:%M')}")
    
    view = View(timeout=300)
    
    # Backup erstellen
    backup_button = Button(label="💾 Backup", style=discord.ButtonStyle.success)
    backup_button.callback = lambda i: create_bot_backup(i)
    
    # Export/Import
    export_button = Button(label="📤 Export", style=discord.ButtonStyle.primary)
    export_button.callback = lambda i: export_all_config(i)
    
    # Zurück zum Admin-Panel
    back_button = Button(label="⬅️ Admin Panel", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: admin_config_command(i)
    
    view.add_item(backup_button)
    view.add_item(export_button)
    view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def create_bot_backup(interaction):
    """Erstelle automatisches Backup aller Bot-Daten"""
    try:
        import datetime
        import shutil
        import os
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_folder = f"backup_{timestamp}"
        
        # Erstelle Backup-Ordner
        os.makedirs(backup_folder, exist_ok=True)
        
        # Wichtige Dateien sichern
        files_to_backup = [
            'prices.json',
            'server_configs.json', 
            'discount_codes.json',
            'appointments.json',
            'pending_tickets.json'
        ]
        
        backed_up_files = []
        for file in files_to_backup:
            if os.path.exists(file):
                shutil.copy2(file, backup_folder)
                backed_up_files.append(file)
        
        embed = discord.Embed(
            title="✅ Backup erfolgreich erstellt",
            description=f"Alle Bot-Daten wurden in `{backup_folder}` gesichert!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📄 Gesicherte Dateien:",
            value="\n".join([f"• {file}" for file in backed_up_files]),
            inline=False
        )
        
        print(f"✅ Backup erstellt: {backup_folder}")
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Backup-Fehler",
            description=f"Fehler beim Erstellen des Backups: {str(e)}",
            color=0xff0000
        )
        print(f"❌ Backup-Fehler: {e}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def export_all_config(interaction):
    """Exportiere vollständige Bot-Konfiguration"""
    try:
        import datetime
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sammle alle Konfigurationsdaten
        export_data = {
            "export_info": {
                "timestamp": timestamp,
                "server_name": interaction.guild.name,
                "server_id": interaction.guild.id,
                "bot_version": "2.5.0"
            }
        }
        
        # Preise laden
        try:
            with open('prices.json', 'r', encoding='utf-8') as f:
                export_data['prices'] = json.load(f)
        except:
            export_data['prices'] = {}
        
        # Discount-Codes laden
        try:
            with open('discount_codes.json', 'r', encoding='utf-8') as f:
                export_data['discount_codes'] = json.load(f)
        except:
            export_data['discount_codes'] = {}
        
        # Export-Datei erstellen
        export_filename = f"haze_bot_config_{timestamp}.json"
        with open(export_filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        embed = discord.Embed(
            title="✅ Export erfolgreich",
            description=f"Konfiguration exportiert als `{export_filename}`",
            color=0x00ff00
        )
        
        data_summary = f"📦 **Preiskategorien:** {len(export_data['prices'])}\n"
        data_summary += f"🎟️ **Discount-Codes:** {len(export_data['discount_codes'])}"
        
        embed.add_field(
            name="📊 Exportierte Daten:",
            value=data_summary,
            inline=False
        )
        
        print(f"✅ Konfiguration exportiert: {export_filename}")
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Export-Fehler",
            description=f"Fehler beim Exportieren: {str(e)}",
            color=0xff0000
        )
        print(f"❌ Export-Fehler: {e}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def export_config(interaction):
    await interaction.response.send_message("🚧 Konfiguration Export wird noch entwickelt...", ephemeral=True)

async def show_import_modal(interaction):
    await interaction.response.send_message("🚧 Konfiguration Import wird noch entwickelt...", ephemeral=True)

# Kategorien-Management Modals und Funktionen

class CategoryEditModal(Modal):
    def __init__(self, server_config):
        super().__init__(title="📂 Kategorien bearbeiten")
        
        categories = server_config.get("categories", {})
        
        self.open_cat = TextInput(
            label="📋 Offene Tickets Kategorie ID",
            placeholder="z.B. 1234567890123456789",
            default=str(categories.get("open", "")),
            required=False,
            max_length=20
        )
        
        self.claimed_cat = TextInput(
            label="🔧 In Bearbeitung Kategorie ID", 
            placeholder="z.B. 1234567890123456789",
            default=str(categories.get("claimed", "")),
            required=False,
            max_length=20
        )
        
        self.paid_cat = TextInput(
            label="💰 Bezahlt Kategorie ID",
            placeholder="z.B. 1234567890123456789", 
            default=str(categories.get("paid", "")),
            required=False,
            max_length=20
        )
        
        self.finished_cat = TextInput(
            label="✅ Abgeschlossen Kategorie ID",
            placeholder="z.B. 1234567890123456789",
            default=str(categories.get("finished", "")),
            required=False,
            max_length=20
        )
        
        self.add_item(self.open_cat)
        self.add_item(self.claimed_cat)
        self.add_item(self.paid_cat)
        self.add_item(self.finished_cat)
    
    async def on_submit(self, interaction: discord.Interaction):
        server_config = get_server_config(interaction.guild.id)
        
        # Update categories
        if not "categories" in server_config:
            server_config["categories"] = {}
        
        if self.open_cat.value.strip():
            try:
                server_config["categories"]["open"] = int(self.open_cat.value.strip())
            except ValueError:
                await interaction.response.send_message("❌ Ungültige ID für Offene Tickets", ephemeral=True)
                return
        
        if self.claimed_cat.value.strip():
            try:
                server_config["categories"]["claimed"] = int(self.claimed_cat.value.strip())
            except ValueError:
                await interaction.response.send_message("❌ Ungültige ID für In Bearbeitung", ephemeral=True)
                return
        
        if self.paid_cat.value.strip():
            try:
                server_config["categories"]["paid"] = int(self.paid_cat.value.strip())
            except ValueError:
                await interaction.response.send_message("❌ Ungültige ID für Bezahlt", ephemeral=True)
                return
        
        if self.finished_cat.value.strip():
            try:
                server_config["categories"]["finished"] = int(self.finished_cat.value.strip())
            except ValueError:
                await interaction.response.send_message("❌ Ungültige ID für Abgeschlossen", ephemeral=True)
                return
        
        save_server_config(interaction.guild.id, server_config)
        
        await interaction.response.send_message("✅ Kategorien erfolgreich aktualisiert!", ephemeral=True)

async def show_category_edit_modal(interaction):
    server_config = get_server_config(interaction.guild.id)
    modal = CategoryEditModal(server_config)
    await interaction.response.send_modal(modal)

async def auto_setup_categories(interaction):
    """Automatisches Setup der Ticket-Kategorien"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        
        # Kategorien erstellen
        categories = {}
        
        open_cat = await guild.create_category("📋 Offene Tickets")
        categories["open"] = open_cat.id
        
        claimed_cat = await guild.create_category("🔧 In Bearbeitung")
        categories["claimed"] = claimed_cat.id
        
        paid_cat = await guild.create_category("💰 Bezahlt")
        categories["paid"] = paid_cat.id
        
        finished_cat = await guild.create_category("✅ Abgeschlossen")
        categories["finished"] = finished_cat.id
        
        # Konfiguration speichern
        server_config = get_server_config(guild.id)
        server_config["categories"] = categories
        save_server_config(guild.id, server_config)
        
        # Ticket Counter erstellen
        try:
            await open_cat.create_voice_channel("📊 Offene Tickets: 0")
        except:
            pass
        
        embed = discord.Embed(
            title="✅ Auto-Setup abgeschlossen!",
            description="Alle Ticket-Kategorien wurden erstellt:",
            color=0x00ff00
        )
        
        setup_info = f"""
📋 **Offene Tickets:** {open_cat.mention}
🔧 **In Bearbeitung:** {claimed_cat.mention}
💰 **Bezahlt:** {paid_cat.mention}
✅ **Abgeschlossen:** {finished_cat.mention}
📊 **Ticket Counter** erstellt
        """
        
        embed.add_field(
            name="🎯 Erstellt:",
            value=setup_info.strip(),
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Auto-Setup Fehler",
            description=f"Fehler beim Erstellen der Kategorien: {str(e)}",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)

async def reset_config(interaction):
    """Konfiguration zurücksetzen mit Bestätigung"""
    embed = discord.Embed(
        title="⚠️ Konfiguration zurücksetzen",
        description="**ACHTUNG:** Diese Aktion löscht alle Bot-Einstellungen!\n\n• Alle Preise werden gelöscht\n• Rollen-Konfiguration wird zurückgesetzt\n• Kategorien-Zuweisungen entfernt\n• Branding auf Standard zurückgesetzt\n\n**Diese Aktion kann nicht rückgängig gemacht werden!**",
        color=0xff0000
    )
    
    view = View(timeout=60)
    
    # Bestätigen
    confirm_button = Button(label="🗑️ Ja, alles löschen", style=discord.ButtonStyle.danger)
    confirm_button.callback = lambda i: confirm_reset_config(i)
    
    # Abbrechen  
    cancel_button = Button(label="❌ Abbrechen", style=discord.ButtonStyle.secondary)
    cancel_button.callback = lambda i: admin_config_command(i)
    
    view.add_item(confirm_button)
    view.add_item(cancel_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def confirm_reset_config(interaction):
    """Konfiguration tatsächlich zurücksetzen"""
    try:
        # Auf Standard-Konfiguration zurücksetzen
        default_config = get_default_config()
        save_server_config(interaction.guild.id, default_config)
        
        embed = discord.Embed(
            title="✅ Konfiguration zurückgesetzt",
            description="Alle Bot-Einstellungen wurden auf Standard zurückgesetzt.\n\nDu kannst jetzt ein neues Setup durchführen oder die Einstellungen manuell konfigurieren.",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Reset Fehler",
            description=f"Fehler beim Zurücksetzen: {str(e)}",
            color=0xff0000
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

# Calendar system functions
async def generate_weekly_calendar():
    """Generate and display the weekly appointment calendar"""
    try:
        berlin_tz = pytz.timezone('Europe/Berlin')
        now = datetime.now(berlin_tz)
        
        # Get the start of current week (Monday)
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Load current appointments
        try:
            with open('appointments.json', 'r', encoding='utf-8') as f:
                appointments = json.load(f)
        except FileNotFoundError:
            appointments = {}
        
        # Generate calendar for current week
        calendar_text = "📅 **HAZE VISUALS - APPOINTMENT CALENDAR**\n"
        calendar_text += "=" * 50 + "\n\n"
        
        total_slots = 0
        booked_slots = 0
        
        for day_offset in range(7):  # Monday to Sunday
            current_day = start_of_week + timedelta(days=day_offset)
            day_name = current_day.strftime('%A')
            day_date = current_day.strftime('%d.%m.%Y')
            
            calendar_text += f"**{day_name}, {day_date}**\n"
            
            # Generate time slots from 18:00 to 22:00 (30-minute intervals)
            available_slots = []
            unavailable_slots = []
            
            for hour in range(18, 22):
                for minute in [0, 30]:
                    time_slot = f"{hour:02d}:{minute:02d}"
                    slot_datetime = current_day.replace(hour=hour, minute=minute)
                    slot_key = slot_datetime.strftime('%Y-%m-%d_%H:%M')
                    
                    total_slots += 1
                    
                    if slot_key in appointments:
                        unavailable_slots.append(f"🔴 {time_slot} - Gebucht ({appointments[slot_key]['user_name']})")
                        booked_slots += 1
                    else:
                        available_slots.append(f"🟢 {time_slot} - Verfügbar")
            
            # Add slots to calendar
            all_slots = available_slots + unavailable_slots
            for slot in all_slots:
                calendar_text += f"  {slot}\n"
            
            calendar_text += "\n"
        
        # Add summary
        free_slots = total_slots - booked_slots
        calendar_text += f"📊 **ZUSAMMENFASSUNG:**\n"
        calendar_text += f"✅ Verfügbare Termine: **{free_slots}**\n"
        calendar_text += f"❌ Gebuchte Termine: **{booked_slots}**\n"
        calendar_text += f"📅 Gesamt Termine: **{total_slots}**\n\n"
        calendar_text += f"🕐 **Öffnungszeiten:** Montag - Sonntag, 18:00 - 22:00 Uhr\n"
        calendar_text += f"⏰ **Termin-Dauer:** 30 Minuten\n"
        calendar_text += f"📍 **Zeitzone:** Berlin (CET/CEST)\n\n"
        calendar_text += f"💡 *Termine werden automatisch über das Ticket-System gebucht!*"
        
        return calendar_text
        
    except Exception as e:
        print(f"❌ Fehler beim Generieren des Kalenders: {e}")
        return "❌ Fehler beim Laden des Kalenders."

async def update_calendar_display():
    """Update the calendar display in the designated channel"""
    try:
        # Get calendar channel from server config (fallback to hardcoded for existing server)
        calendar_channel_id = 1413668409853345792  # Default for existing server
        
        # Try to get from server configs for other servers
        for guild in bot.guilds:
            config = get_server_config(guild.id)
            if config["channels"]["calendar_channel"]:
                calendar_channel_id = config["channels"]["calendar_channel"]
                break
        
        calendar_channel = bot.get_channel(calendar_channel_id)
        if not calendar_channel:
            print("❌ Kalender-Channel nicht gefunden")
            return
        
        # Generate new calendar
        calendar_text = await generate_weekly_calendar()
        
        # Clear old messages (keep only last 10 messages)
        async for message in calendar_channel.history(limit=50):
            if message.author == bot.user:
                await message.delete()
        
        # Send new calendar
        # Split message if too long (Discord limit is 2000 characters)
        if len(calendar_text) > 2000:
            # Split into chunks
            chunks = []
            current_chunk = ""
            lines = calendar_text.split('\n')
            
            for line in lines:
                if len(current_chunk + line + '\n') > 1900:  # Leave some buffer
                    chunks.append(current_chunk)
                    current_chunk = line + '\n'
                else:
                    current_chunk += line + '\n'
            
            if current_chunk:
                chunks.append(current_chunk)
            
            # Send chunks
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await calendar_channel.send(f"```\n{chunk}\n```")
                else:
                    await calendar_channel.send(f"```\n{chunk}\n```")
        else:
            await calendar_channel.send(f"```\n{calendar_text}\n```")
        
        print("📅 Kalender erfolgreich aktualisiert")
        
    except Exception as e:
        print(f"❌ Fehler beim Aktualisieren des Kalenders: {e}")

# Weekly calendar update task (runs every Saturday at 00:00 Berlin time)
@tasks.loop(hours=24)  # Check daily
async def weekly_calendar_update():
    """Update calendar and cleanup old appointments every Saturday"""
    try:
        berlin_tz = pytz.timezone('Europe/Berlin')
        now = datetime.now(berlin_tz)
        
        # Check if it's Saturday at midnight (or within the hour)
        if now.weekday() == 5 and now.hour == 0:  # Saturday = 5, Sunday = 6
            print("📅 Saturday cleanup: Clearing old appointments...")
            
            # Load current appointments
            try:
                with open('appointments.json', 'r', encoding='utf-8') as f:
                    appointments = json.load(f)
            except FileNotFoundError:
                appointments = {}
            
            # Calculate cutoff date (start of current week)
            start_of_week = now - timedelta(days=now.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Remove old appointments (from previous weeks)
            appointments_to_remove = []
            for slot_key in appointments:
                try:
                    slot_datetime = datetime.strptime(slot_key, '%Y-%m-%d_%H:%M')
                    slot_datetime = berlin_tz.localize(slot_datetime)
                    
                    if slot_datetime < start_of_week:
                        appointments_to_remove.append(slot_key)
                except ValueError:
                    continue
            
            # Remove old appointments
            for slot_key in appointments_to_remove:
                del appointments[slot_key]
            
            # Save updated appointments
            with open('appointments.json', 'w', encoding='utf-8') as f:
                json.dump(appointments, f, ensure_ascii=False, indent=2)
            
            print(f"🗑️ {len(appointments_to_remove)} alte Termine entfernt")
            
            # Force calendar update
            await update_calendar_display()
        
        # Update calendar daily at 6 AM
        elif now.hour == 6:
            await update_calendar_display()
            
    except Exception as e:
        print(f"❌ Fehler in weekly_calendar_update: {e}")

@weekly_calendar_update.before_loop
async def before_weekly_calendar_update():
    """Wait for bot to be ready before starting the task"""
    await bot.wait_until_ready()
    # Initial calendar display
    await update_calendar_display()

# Background task for checking unresponded tickets
@tasks.loop(minutes=5)  # Check every 5 minutes
async def check_tickets_task():
    """Background task to check for unresponded tickets"""
    await check_and_ping_unresponded_tickets(bot)

@check_tickets_task.before_loop
async def before_check_tickets_task():
    """Wait for bot to be ready before starting the task"""
    await bot.wait_until_ready()


# ========================================
# SHOP CATEGORIES MANAGEMENT
# ========================================

async def show_shop_categories_config(interaction):
    """Shop-Kategorien mit Farben verwalten"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    # Lade Shop-Kategorien (erstelle falls nicht vorhanden)
    shop_categories = load_shop_categories()
    
    embed = discord.Embed(
        title="🛍️ Shop-Kategorien Verwaltung",
        description="Verwalte deine Shop-Produktkategorien mit Farben und Preisen:",
        color=0x9b59b6
    )
    
    # Zeige aktuelle Kategorien
    if shop_categories:
        categories_text = ""
        for category_name, category_data in shop_categories.items():
            color = category_data.get("color", "#ffffff")
            products_count = len(category_data.get("products", {}))
            categories_text += f"**{category_name}**\n"
            categories_text += f"🎨 Farbe: `{color}`\n"
            categories_text += f"📦 Produkte: {products_count}\n\n"
    else:
        categories_text = "Keine Kategorien vorhanden\n\n**Standard-Setup verfügbar:**\nKlicke auf 'Standard-Setup' um die Haze Visuals Kategorien zu erstellen."
    
    embed.add_field(
        name="📂 Aktuelle Kategorien",
        value=categories_text[:1024],  # Discord limit
        inline=False
    )
    
    shop_view = View(timeout=300)
    
    # Kategorie hinzufügen
    add_category_button = Button(label="➕ Kategorie hinzufügen", style=discord.ButtonStyle.success)
    add_category_button.callback = lambda i: show_add_shop_category_modal(i)
    
    # Kategorie bearbeiten
    edit_category_button = Button(label="✏️ Kategorie bearbeiten", style=discord.ButtonStyle.primary)
    edit_category_button.callback = lambda i: show_edit_shop_category_modal(i)
    
    # Produkt hinzufügen
    add_product_button = Button(label="📦 Produkt hinzufügen", style=discord.ButtonStyle.secondary)
    add_product_button.callback = lambda i: show_add_shop_product_modal(i)
    
    # Produkt bearbeiten
    edit_product_button = Button(label="✏️ Produkt bearbeiten", style=discord.ButtonStyle.primary)
    edit_product_button.callback = lambda i: show_edit_shop_product_modal(i)
    
    # Standard-Setup (nur wenn keine Kategorien vorhanden)
    if not shop_categories:
        default_setup_button = Button(label="🚀 Standard-Setup", style=discord.ButtonStyle.blurple)
        default_setup_button.callback = lambda i: create_default_shop_categories(i)
        shop_view.add_item(default_setup_button)
    
    # Produkt löschen
    delete_product_button = Button(label="🗑️ Produkt löschen", style=discord.ButtonStyle.danger)
    delete_product_button.callback = lambda i: show_delete_shop_product_modal(i)
    
    # Kategorie löschen
    delete_category_button = Button(label="❌ Kategorie löschen", style=discord.ButtonStyle.danger)
    delete_category_button.callback = lambda i: show_delete_shop_category_modal(i)
    
    # Zurück
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.secondary)
    back_button.callback = lambda i: show_pricing_config(i)
    
    # Erste Reihe
    shop_view.add_item(add_category_button)
    shop_view.add_item(edit_category_button)
    shop_view.add_item(add_product_button)
    shop_view.add_item(edit_product_button)
    
    # Zweite Reihe
    shop_view.add_item(delete_product_button)
    shop_view.add_item(delete_category_button)
    shop_view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=shop_view, ephemeral=True)

def load_shop_categories():
    """Lade Shop-Kategorien aus JSON-Datei"""
    try:
        with open('shop_categories.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_shop_categories(categories):
    """Speichere Shop-Kategorien in JSON-Datei"""
    try:
        with open('shop_categories.json', 'w', encoding='utf-8') as f:
            json.dump(categories, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Shop-Kategorien: {e}")
        return False

async def create_default_shop_categories(interaction):
    """Erstelle Standard-Haze-Visuals Kategorien"""
    default_categories = {
        "Soundpacks": {
            "color": "#3498db",
            "description": "Hochwertige Audio-Pakete",
            "products": {
                "Soundpack v1": {
                    "price": "25€",
                    "description": "Premium Audio-Sammlung mit hochwertigen Beats und Loops"
                }
            }
        },
        "Templates/Blender": {
            "color": "#e74c3c", 
            "description": "Design-Vorlagen und 3D-Ressourcen",
            "products": {
                "Showroom": {
                    "price": "45€",
                    "description": "Professionelle Präsentations-Templates"
                },
                "Premium Template": {
                    "price": "35€",
                    "description": "Hochwertige Design-Vorlagen"
                },
                "Basic Template": {
                    "price": "20€",
                    "description": "Einfache, saubere Templates"
                }
            }
        },
        "Discord Bots": {
            "color": "#9b59b6",
            "description": "Maßgeschneiderte Bot-Lösungen",
            "products": {
                "Ticket und Management Bot": {
                    "price": "75€",
                    "description": "Vollständige Server-Verwaltung mit Ticket-System"
                },
                "Aktivitätschecker (FiveM)": {
                    "price": "60€", 
                    "description": "Speziell für FiveM-Server mit Spielzeit-Tracking"
                }
            }
        }
    }
    
    if save_shop_categories(default_categories):
        await interaction.response.send_message(
            "✅ **Standard-Kategorien erstellt!**\n\n"
            "🎵 **Soundpacks** (blau)\n"
            "🎨 **Templates/Blender** (rot)\n"
            "🤖 **Discord Bots** (lila)\n\n"
            "Alle Kategorien wurden mit den Standard-Produkten und -Preisen eingerichtet.",
            ephemeral=True
        )
        print("✅ Standard-Shop-Kategorien erstellt")
        
        # Zeige aktualisierte Übersicht
        await asyncio.sleep(2)
        await show_shop_categories_config(interaction)
    else:
        await interaction.response.send_message(
            "❌ Fehler beim Erstellen der Standard-Kategorien.",
            ephemeral=True
        )

# ========================================
# SHOP CATEGORY MODALS
# ========================================

class AddShopCategoryModal(Modal):
    def __init__(self):
        super().__init__(title="➕ Neue Shop-Kategorie erstellen")
        
        self.category_name = TextInput(
            label="📂 Kategorie-Name",
            placeholder="z.B. Soundpacks, Templates, Discord Bots...",
            required=True,
            max_length=50
        )
        
        self.color = TextInput(
            label="🎨 Farbe (Hex-Code)",
            placeholder="#3498db oder 3498db",
            required=True,
            max_length=7,
            min_length=6
        )
        
        self.description = TextInput(
            label="📝 Beschreibung",
            placeholder="Kurze Beschreibung der Kategorie...",
            required=False,
            max_length=200
        )
        
        self.add_item(self.category_name)
        self.add_item(self.color)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validiere Farbe
            color_value = self.color.value.strip()
            if not color_value.startswith('#'):
                color_value = '#' + color_value
            
            # Überprüfe Hex-Format
            if not all(c in '0123456789ABCDEFabcdef' for c in color_value[1:]):
                await interaction.response.send_message(
                    "❌ Ungültiger Hex-Code! Verwende Format: #3498db oder 3498db",
                    ephemeral=True
                )
                return
            
            shop_categories = load_shop_categories()
            
            # Prüfe ob Kategorie bereits existiert
            if self.category_name.value in shop_categories:
                await interaction.response.send_message(
                    f"❌ Kategorie '{self.category_name.value}' existiert bereits!",
                    ephemeral=True
                )
                return
            
            # Neue Kategorie hinzufügen
            shop_categories[self.category_name.value] = {
                "color": color_value,
                "description": self.description.value or "Keine Beschreibung",
                "products": {}
            }
            
            if save_shop_categories(shop_categories):
                await interaction.response.send_message(
                    f"✅ **Kategorie erstellt!**\n\n"
                    f"📂 **Name:** {self.category_name.value}\n"
                    f"🎨 **Farbe:** {color_value}\n"
                    f"📝 **Beschreibung:** {self.description.value or 'Keine'}\n\n"
                    f"Du kannst jetzt Produkte zu dieser Kategorie hinzufügen.",
                    ephemeral=True
                )
                print(f"✅ Shop-Kategorie '{self.category_name.value}' erstellt")
            else:
                await interaction.response.send_message(
                    "❌ Fehler beim Speichern der Kategorie.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Fehler beim Erstellen der Shop-Kategorie: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

class AddShopProductModal(Modal):
    def __init__(self):
        super().__init__(title="📦 Neues Produkt hinzufügen")
        
        self.category_name = TextInput(
            label="📂 Kategorie-Name",
            placeholder="In welche Kategorie? (z.B. Soundpacks)",
            required=True,
            max_length=50
        )
        
        self.product_name = TextInput(
            label="🎯 Produkt-Name",
            placeholder="z.B. Soundpack v1, Premium Template...",
            required=True,
            max_length=100
        )
        
        self.price = TextInput(
            label="💰 Preis",
            placeholder="z.B. 25€, 50€, 100€...",
            required=True,
            max_length=20
        )
        
        self.description = TextInput(
            label="📝 Produktbeschreibung",
            placeholder="Kurze Beschreibung des Produkts...",
            required=False,
            max_length=300,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.category_name)
        self.add_item(self.product_name)
        self.add_item(self.price)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            shop_categories = load_shop_categories()
            
            # Prüfe ob Kategorie existiert
            if self.category_name.value not in shop_categories:
                available_categories = ", ".join(shop_categories.keys()) if shop_categories else "Keine"
                await interaction.response.send_message(
                    f"❌ Kategorie '{self.category_name.value}' existiert nicht!\n\n"
                    f"**Verfügbare Kategorien:** {available_categories}",
                    ephemeral=True
                )
                return
            
            # Prüfe ob Produkt bereits existiert
            if self.product_name.value in shop_categories[self.category_name.value]["products"]:
                await interaction.response.send_message(
                    f"❌ Produkt '{self.product_name.value}' existiert bereits in '{self.category_name.value}'!",
                    ephemeral=True
                )
                return
            
            # Produkt hinzufügen
            shop_categories[self.category_name.value]["products"][self.product_name.value] = {
                "price": self.price.value,
                "description": self.description.value or "Keine Beschreibung"
            }
            
            if save_shop_categories(shop_categories):
                await interaction.response.send_message(
                    f"✅ **Produkt hinzugefügt!**\n\n"
                    f"📂 **Kategorie:** {self.category_name.value}\n"
                    f"🎯 **Produkt:** {self.product_name.value}\n"
                    f"💰 **Preis:** {self.price.value}\n"
                    f"📝 **Beschreibung:** {self.description.value or 'Keine'}\n\n"
                    f"Das Produkt ist jetzt im Shop-System verfügbar!",
                    ephemeral=True
                )
                print(f"✅ Produkt '{self.product_name.value}' zu '{self.category_name.value}' hinzugefügt")
            else:
                await interaction.response.send_message(
                    "❌ Fehler beim Speichern des Produkts.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Fehler beim Hinzufügen des Produkts: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

async def show_add_shop_category_modal(interaction):
    """Zeige Modal zum Hinzufügen einer Shop-Kategorie"""
    modal = AddShopCategoryModal()
    await interaction.response.send_modal(modal)

async def show_add_shop_product_modal(interaction):
    """Zeige Modal zum Hinzufügen eines Shop-Produkts"""
    modal = AddShopProductModal()
    await interaction.response.send_modal(modal)

# ========================================
# ERWEITERTE SHOP CATEGORY MODALS
# ========================================

class SelectCategoryToEditModal(Modal):
    def __init__(self):
        super().__init__(title="✏️ Kategorie zum Bearbeiten auswählen")
        
        shop_categories = load_shop_categories()
        categories_list = ", ".join(shop_categories.keys()) if shop_categories else "Keine verfügbar"
        
        self.category_name = TextInput(
            label="📂 Kategorie-Name",
            placeholder=f"Verfügbar: {categories_list}",
            required=True,
            max_length=50
        )
        
        self.add_item(self.category_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            shop_categories = load_shop_categories()
            
            if self.category_name.value not in shop_categories:
                available_categories = ", ".join(shop_categories.keys()) if shop_categories else "Keine"
                await interaction.response.send_message(
                    f"❌ Kategorie '{self.category_name.value}' nicht gefunden!\n\n"
                    f"**Verfügbare Kategorien:** {available_categories}",
                    ephemeral=True
                )
                return
            
            # Zeige Edit-Modal für die ausgewählte Kategorie
            category_data = shop_categories[self.category_name.value]
            edit_modal = EditShopCategoryModal(self.category_name.value, category_data)
            await interaction.response.send_modal(edit_modal)
            
        except Exception as e:
            print(f"❌ Fehler beim Auswählen der Kategorie: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

class EditShopCategoryModal(Modal):
    def __init__(self, category_name, category_data):
        super().__init__(title=f"✏️ '{category_name}' bearbeiten")
        self.original_name = category_name
        
        self.category_name = TextInput(
            label="📂 Kategorie-Name",
            placeholder="Neuer Name für die Kategorie",
            default=category_name,
            required=True,
            max_length=50
        )
        
        self.color = TextInput(
            label="🎨 Farbe (Hex-Code)",
            placeholder="#3498db oder 3498db",
            default=category_data.get("color", "#9b59b6"),
            required=True,
            max_length=7,
            min_length=6
        )
        
        self.description = TextInput(
            label="📝 Beschreibung",
            placeholder="Beschreibung der Kategorie...",
            default=category_data.get("description", ""),
            required=False,
            max_length=200
        )
        
        self.add_item(self.category_name)
        self.add_item(self.color)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validiere Farbe
            color_value = self.color.value.strip()
            if not color_value.startswith('#'):
                color_value = '#' + color_value
            
            # Überprüfe Hex-Format
            if not all(c in '0123456789ABCDEFabcdef' for c in color_value[1:]):
                await interaction.response.send_message(
                    "❌ Ungültiger Hex-Code! Verwende Format: #3498db oder 3498db",
                    ephemeral=True
                )
                return
            
            shop_categories = load_shop_categories()
            
            # Prüfe ob der neue Name bereits existiert (außer es ist der gleiche)
            if (self.category_name.value != self.original_name and 
                self.category_name.value in shop_categories):
                await interaction.response.send_message(
                    f"❌ Kategorie '{self.category_name.value}' existiert bereits!",
                    ephemeral=True
                )
                return
            
            # Speichere die vorhandenen Produkte
            existing_products = shop_categories[self.original_name].get("products", {})
            
            # Entferne die alte Kategorie falls Name geändert wurde
            if self.category_name.value != self.original_name:
                del shop_categories[self.original_name]
            
            # Aktualisiere/Erstelle die Kategorie
            shop_categories[self.category_name.value] = {
                "color": color_value,
                "description": self.description.value or "Keine Beschreibung",
                "products": existing_products
            }
            
            if save_shop_categories(shop_categories):
                await interaction.response.send_message(
                    f"✅ **Kategorie aktualisiert!**\n\n"
                    f"📂 **Name:** {self.category_name.value}\n"
                    f"🎨 **Farbe:** {color_value}\n"
                    f"📝 **Beschreibung:** {self.description.value or 'Keine'}\n"
                    f"📦 **Produkte:** {len(existing_products)} erhalten\n\n"
                    f"Alle Änderungen sind sofort im Shop verfügbar!",
                    ephemeral=True
                )
                print(f"✅ Shop-Kategorie '{self.original_name}' zu '{self.category_name.value}' aktualisiert")
            else:
                await interaction.response.send_message(
                    "❌ Fehler beim Speichern der Kategorie.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Fehler beim Bearbeiten der Shop-Kategorie: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

class SelectCategoryToDeleteModal(Modal):
    def __init__(self):
        super().__init__(title="🗑️ Kategorie zum Löschen auswählen")
        
        shop_categories = load_shop_categories()
        categories_list = ", ".join(shop_categories.keys()) if shop_categories else "Keine verfügbar"
        
        self.category_name = TextInput(
            label="📂 Kategorie-Name",
            placeholder=f"Verfügbar: {categories_list}",
            required=True,
            max_length=50
        )
        
        self.confirmation = TextInput(
            label="⚠️ Bestätigung (schreibe 'LÖSCHEN')",
            placeholder="Schreibe LÖSCHEN um zu bestätigen",
            required=True,
            max_length=10
        )
        
        self.add_item(self.category_name)
        self.add_item(self.confirmation)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.confirmation.value.upper() != "LÖSCHEN":
                await interaction.response.send_message(
                    "❌ Löschung nicht bestätigt. Schreibe 'LÖSCHEN' um zu bestätigen.",
                    ephemeral=True
                )
                return
            
            shop_categories = load_shop_categories()
            
            if self.category_name.value not in shop_categories:
                available_categories = ", ".join(shop_categories.keys()) if shop_categories else "Keine"
                await interaction.response.send_message(
                    f"❌ Kategorie '{self.category_name.value}' nicht gefunden!\n\n"
                    f"**Verfügbare Kategorien:** {available_categories}",
                    ephemeral=True
                )
                return
            
            # Zähle Produkte vor dem Löschen
            products_count = len(shop_categories[self.category_name.value].get("products", {}))
            
            # Lösche die Kategorie
            del shop_categories[self.category_name.value]
            
            if save_shop_categories(shop_categories):
                await interaction.response.send_message(
                    f"✅ **Kategorie gelöscht!**\n\n"
                    f"🗑️ **Gelöscht:** {self.category_name.value}\n"
                    f"📦 **Produkte entfernt:** {products_count}\n\n"
                    f"⚠️ Diese Änderung kann nicht rückgängig gemacht werden!",
                    ephemeral=True
                )
                print(f"🗑️ Shop-Kategorie '{self.category_name.value}' gelöscht ({products_count} Produkte)")
            else:
                await interaction.response.send_message(
                    "❌ Fehler beim Löschen der Kategorie.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Fehler beim Löschen der Shop-Kategorie: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

# ========================================
# PRODUKT-VERWALTUNG MODALS
# ========================================

class SelectProductToEditModal(Modal):
    def __init__(self):
        super().__init__(title="✏️ Produkt zum Bearbeiten auswählen")
        
        self.category_name = TextInput(
            label="📂 Kategorie-Name",
            placeholder="In welcher Kategorie? (z.B. Soundpacks)",
            required=True,
            max_length=50
        )
        
        self.product_name = TextInput(
            label="🎯 Produkt-Name",
            placeholder="Welches Produkt bearbeiten?",
            required=True,
            max_length=100
        )
        
        self.add_item(self.category_name)
        self.add_item(self.product_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            shop_categories = load_shop_categories()
            
            if self.category_name.value not in shop_categories:
                available_categories = ", ".join(shop_categories.keys()) if shop_categories else "Keine"
                await interaction.response.send_message(
                    f"❌ Kategorie '{self.category_name.value}' nicht gefunden!\n\n"
                    f"**Verfügbare Kategorien:** {available_categories}",
                    ephemeral=True
                )
                return
            
            products = shop_categories[self.category_name.value].get("products", {})
            if self.product_name.value not in products:
                available_products = ", ".join(products.keys()) if products else "Keine"
                await interaction.response.send_message(
                    f"❌ Produkt '{self.product_name.value}' nicht gefunden in '{self.category_name.value}'!\n\n"
                    f"**Verfügbare Produkte:** {available_products}",
                    ephemeral=True
                )
                return
            
            # Zeige Edit-Modal für das ausgewählte Produkt
            product_data = products[self.product_name.value]
            edit_modal = EditShopProductModal(self.category_name.value, self.product_name.value, product_data)
            await interaction.response.send_modal(edit_modal)
            
        except Exception as e:
            print(f"❌ Fehler beim Auswählen des Produkts: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

class EditShopProductModal(Modal):
    def __init__(self, category_name, product_name, product_data):
        super().__init__(title=f"✏️ '{product_name}' bearbeiten")
        self.category_name = category_name
        self.original_product_name = product_name
        
        self.product_name = TextInput(
            label="🎯 Produkt-Name",
            placeholder="Neuer Name für das Produkt",
            default=product_name,
            required=True,
            max_length=100
        )
        
        self.price = TextInput(
            label="💰 Preis",
            placeholder="z.B. 25€, 50€, 100€...",
            default=product_data.get("price", ""),
            required=True,
            max_length=20
        )
        
        self.description = TextInput(
            label="📝 Produktbeschreibung",
            placeholder="Beschreibung des Produkts...",
            default=product_data.get("description", ""),
            required=False,
            max_length=300,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.product_name)
        self.add_item(self.price)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            shop_categories = load_shop_categories()
            
            if self.category_name not in shop_categories:
                await interaction.response.send_message(
                    f"❌ Kategorie '{self.category_name}' nicht mehr vorhanden!",
                    ephemeral=True
                )
                return
            
            products = shop_categories[self.category_name]["products"]
            
            # Prüfe ob neuer Produktname bereits existiert (außer es ist der gleiche)
            if (self.product_name.value != self.original_product_name and 
                self.product_name.value in products):
                await interaction.response.send_message(
                    f"❌ Produkt '{self.product_name.value}' existiert bereits in '{self.category_name}'!",
                    ephemeral=True
                )
                return
            
            # Entferne das alte Produkt falls Name geändert wurde
            if self.product_name.value != self.original_product_name:
                del products[self.original_product_name]
            
            # Aktualisiere/Erstelle das Produkt
            products[self.product_name.value] = {
                "price": self.price.value,
                "description": self.description.value or "Keine Beschreibung"
            }
            
            if save_shop_categories(shop_categories):
                await interaction.response.send_message(
                    f"✅ **Produkt aktualisiert!**\n\n"
                    f"📂 **Kategorie:** {self.category_name}\n"
                    f"🎯 **Produkt:** {self.product_name.value}\n"
                    f"💰 **Preis:** {self.price.value}\n"
                    f"📝 **Beschreibung:** {self.description.value or 'Keine'}\n\n"
                    f"Das Produkt ist sofort im Shop verfügbar!",
                    ephemeral=True
                )
                print(f"✅ Produkt '{self.original_product_name}' zu '{self.product_name.value}' aktualisiert")
            else:
                await interaction.response.send_message(
                    "❌ Fehler beim Speichern des Produkts.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Fehler beim Bearbeiten des Produkts: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

class SelectProductToDeleteModal(Modal):
    def __init__(self):
        super().__init__(title="🗑️ Produkt zum Löschen auswählen")
        
        self.category_name = TextInput(
            label="📂 Kategorie-Name",
            placeholder="In welcher Kategorie? (z.B. Soundpacks)",
            required=True,
            max_length=50
        )
        
        self.product_name = TextInput(
            label="🎯 Produkt-Name",
            placeholder="Welches Produkt löschen?",
            required=True,
            max_length=100
        )
        
        self.confirmation = TextInput(
            label="⚠️ Bestätigung (schreibe 'LÖSCHEN')",
            placeholder="Schreibe LÖSCHEN um zu bestätigen",
            required=True,
            max_length=10
        )
        
        self.add_item(self.category_name)
        self.add_item(self.product_name)
        self.add_item(self.confirmation)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.confirmation.value.upper() != "LÖSCHEN":
                await interaction.response.send_message(
                    "❌ Löschung nicht bestätigt. Schreibe 'LÖSCHEN' um zu bestätigen.",
                    ephemeral=True
                )
                return
            
            shop_categories = load_shop_categories()
            
            if self.category_name.value not in shop_categories:
                available_categories = ", ".join(shop_categories.keys()) if shop_categories else "Keine"
                await interaction.response.send_message(
                    f"❌ Kategorie '{self.category_name.value}' nicht gefunden!\n\n"
                    f"**Verfügbare Kategorien:** {available_categories}",
                    ephemeral=True
                )
                return
            
            products = shop_categories[self.category_name.value].get("products", {})
            if self.product_name.value not in products:
                available_products = ", ".join(products.keys()) if products else "Keine"
                await interaction.response.send_message(
                    f"❌ Produkt '{self.product_name.value}' nicht gefunden in '{self.category_name.value}'!\n\n"
                    f"**Verfügbare Produkte:** {available_products}",
                    ephemeral=True
                )
                return
            
            # Speichere Produktinfo für Bestätigung
            product_price = products[self.product_name.value].get("price", "Unbekannt")
            
            # Lösche das Produkt
            del products[self.product_name.value]
            
            if save_shop_categories(shop_categories):
                await interaction.response.send_message(
                    f"✅ **Produkt gelöscht!**\n\n"
                    f"📂 **Kategorie:** {self.category_name.value}\n"
                    f"🗑️ **Gelöscht:** {self.product_name.value}\n"
                    f"💰 **Preis war:** {product_price}\n\n"
                    f"⚠️ Diese Änderung kann nicht rückgängig gemacht werden!",
                    ephemeral=True
                )
                print(f"🗑️ Produkt '{self.product_name.value}' aus '{self.category_name.value}' gelöscht")
            else:
                await interaction.response.send_message(
                    "❌ Fehler beim Löschen des Produkts.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Fehler beim Löschen des Produkts: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

async def show_edit_shop_category_modal(interaction):
    """Zeige Auswahl-Modal zum Bearbeiten einer Shop-Kategorie"""
    shop_categories = load_shop_categories()
    if not shop_categories:
        await interaction.response.send_message(
            "❌ Keine Kategorien vorhanden. Erstelle zuerst eine Kategorie.",
            ephemeral=True
        )
        return
    
    modal = SelectCategoryToEditModal()
    await interaction.response.send_modal(modal)

async def show_delete_shop_category_modal(interaction):
    """Zeige Auswahl-Modal zum Löschen einer Shop-Kategorie"""
    shop_categories = load_shop_categories()
    if not shop_categories:
        await interaction.response.send_message(
            "❌ Keine Kategorien vorhanden.",
            ephemeral=True
        )
        return
    
    modal = SelectCategoryToDeleteModal()
    await interaction.response.send_modal(modal)

async def show_edit_shop_product_modal(interaction):
    """Zeige Auswahl-Modal zum Bearbeiten eines Shop-Produkts"""
    shop_categories = load_shop_categories()
    if not shop_categories:
        await interaction.response.send_message(
            "❌ Keine Kategorien vorhanden. Erstelle zuerst eine Kategorie.",
            ephemeral=True
        )
        return
    
    modal = SelectProductToEditModal()
    await interaction.response.send_modal(modal)

async def show_delete_shop_product_modal(interaction):
    """Zeige Auswahl-Modal zum Löschen eines Shop-Produkts"""
    shop_categories = load_shop_categories()
    if not shop_categories:
        await interaction.response.send_message(
            "❌ Keine Kategorien vorhanden.",
            ephemeral=True
        )
        return
    
    modal = SelectProductToDeleteModal()
    await interaction.response.send_modal(modal)

# ========================================
# DISCOUNT CODE MODAL FOR SHOP TICKETS
# ========================================

class ShopDiscountCodeModal(Modal):
    def __init__(self, category, product_name, original_price, ticket_channel, user):
        super().__init__(title="🎟️ Discount-Code eingeben")
        self.category = category
        self.product_name = product_name
        self.original_price = original_price
        self.ticket_channel = ticket_channel
        self.user = user
        
        self.discount_code = TextInput(
            label="🎟️ Discount-Code",
            placeholder="Gib deinen Rabattcode ein (z.B. SAVE20)...",
            required=True,
            max_length=50,
            min_length=1
        )
        
        self.add_item(self.discount_code)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate and apply discount code
            success, new_price, discount_text, message = validate_and_use_discount_code(
                self.discount_code.value, 
                self.user.id, 
                self.original_price
            )
            
            if success:
                # Create updated embed with new price
                updated_embed = discord.Embed(
                    title="🛍️ Shop-Bestellung (Rabatt angewendet)",
                    description=f"""
**Shop-Bestellung von {self.user.mention}**

📦 **Kategorie:** {self.category}
🎯 **Produkt:** {self.product_name}
💰 **Originalpreis:** ~~{self.original_price}~~
💰 **Neuer Preis:** {new_price}{discount_text}
🎟️ **Rabattcode:** {self.discount_code.value.upper()}
🕐 **Bestellt:** <t:{int(interaction.created_at.timestamp())}:F>

✅ **Rabatt erfolgreich angewendet!**

**Nächste Schritte:**
1. Unser Team prüft deine Bestellung
2. Du erhältst Zahlungsdetails für den **reduzierten Preis**
3. Nach Zahlungseingang beginnen wir mit der Arbeit

📞 Bei Fragen kannst du hier direkt antworten!
                    """,
                    color=0x00ff00
                )
                
                updated_embed.set_footer(text="Haze Visuals • Shop System (Rabatt angewendet)")
                
                # Send confirmation to user
                await interaction.response.send_message(
                    f"✅ **{message}**\n\n"
                    f"📦 **Produkt:** {self.product_name}\n"
                    f"💰 **Alter Preis:** ~~{self.original_price}~~\n"
                    f"💰 **Neuer Preis:** {new_price}{discount_text}\n\n"
                    f"Die Ticketnachricht wurde mit dem neuen Preis aktualisiert!",
                    ephemeral=True
                )
                
                # Update the ticket message (find and edit the original embed)
                try:
                    async for msg in self.ticket_channel.history(limit=10):
                        if msg.author == interaction.client.user and msg.embeds:
                            for embed in msg.embeds:
                                if embed.title and "Shop-Bestellung" in embed.title:
                                    # Update the message with new embed
                                    await msg.edit(embed=updated_embed, view=msg.components[0] if msg.components else None)
                                    break
                            break
                except Exception as e:
                    print(f"❌ Fehler beim Aktualisieren der Ticket-Nachricht: {e}")
                
                # Log discount usage
                print(f"🎟️ Discount Code '{self.discount_code.value}' verwendet von {self.user} in {self.ticket_channel.name}")
                
                # Update pending tickets with new price
                try:
                    with open('pending_tickets.json', 'r') as f:
                        pending_tickets = json.load(f)
                    
                    for ticket_id, ticket_data in pending_tickets.items():
                        if ticket_data.get("user_id") == self.user.id and ticket_data.get("product") == self.product_name:
                            ticket_data["original_price"] = self.original_price
                            ticket_data["discounted_price"] = new_price
                            ticket_data["discount_code"] = self.discount_code.value.upper()
                            ticket_data["discount_text"] = discount_text
                            break
                    
                    with open('pending_tickets.json', 'w') as f:
                        json.dump(pending_tickets, f, indent=2)
                        
                except Exception as e:
                    print(f"❌ Fehler beim Aktualisieren der pending_tickets.json: {e}")
            
            else:
                # Send error message
                await interaction.response.send_message(
                    f"{message}\n\n"
                    f"**Mögliche Gründe:**\n"
                    f"• Code existiert nicht\n"
                    f"• Code bereits verwendet (einmalig nutzbar)\n"
                    f"• Code ist abgelaufen\n\n"
                    f"Kontaktiere das Team falls du einen gültigen Code hast.",
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Fehler beim Anwenden des Discount Codes: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist beim Anwenden des Discount-Codes aufgetreten. "
                "Bitte versuche es erneut oder kontaktiere einen Administrator.",
                ephemeral=True
            )

# ========================================
# ENHANCED DISCOUNT CODE ADMIN MODALS
# ========================================

async def show_add_enhanced_discount_modal(interaction):
    """Zeige erweiterte Modal zum Hinzufügen von Discount-Codes"""
    modal = AddEnhancedDiscountModal()
    await interaction.response.send_modal(modal)

async def show_single_use_discount_modal(interaction):
    """Zeige Modal zum Hinzufügen von einmaligen Discount-Codes"""
    modal = SingleUseDiscountModal()
    await interaction.response.send_modal(modal)

async def show_auto_delete_discount_modal(interaction):
    """Zeige Modal zum Hinzufügen von auto-löschenden Discount-Codes"""
    modal = AutoDeleteDiscountModal()
    await interaction.response.send_modal(modal)

async def show_reset_discount_usage_modal(interaction):
    """Zeige Modal zum Zurücksetzen der Code-Nutzung"""
    modal = ResetDiscountUsageModal()
    await interaction.response.send_modal(modal)

class AddEnhancedDiscountModal(Modal):
    def __init__(self):
        super().__init__(title="➕ Erweiterten Discount-Code hinzufügen")
        
        self.code_name = TextInput(
            label="🎟️ Code-Name",
            placeholder="z.B. SAVE20, WELCOME10, XMAS2024...",
            required=True,
            max_length=20,
            min_length=2
        )
        
        self.discount_type = TextInput(
            label="💰 Rabatt-Typ (percentage/fixed)",
            placeholder="percentage = %, fixed = €",
            default="percentage",
            required=True,
            max_length=10
        )
        
        self.discount_value = TextInput(
            label="🔢 Rabatt-Wert",
            placeholder="Für %: 0.10 (=10%), für €: 5 (=5€)",
            required=True,
            max_length=10
        )
        
        self.max_uses = TextInput(
            label="🔢 Maximale Nutzungen (-1 = unbegrenzt)",
            placeholder="-1 für unbegrenzt, 1 für einmalig, 5 für 5x...",
            default="-1",
            required=True,
            max_length=5
        )
        
        self.description = TextInput(
            label="📝 Beschreibung",
            placeholder="Beschreibung des Discount-Codes...",
            required=False,
            max_length=100
        )
        
        self.add_item(self.code_name)
        self.add_item(self.discount_type)
        self.add_item(self.discount_value)
        self.add_item(self.max_uses)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate inputs
            code = self.code_name.value.upper().strip()
            discount_type = self.discount_type.value.lower().strip()
            
            if discount_type not in ["percentage", "fixed"]:
                await interaction.response.send_message(
                    "❌ Rabatt-Typ muss 'percentage' oder 'fixed' sein!",
                    ephemeral=True
                )
                return
            
            try:
                discount_value = float(self.discount_value.value)
                if discount_type == "percentage" and (discount_value < 0 or discount_value > 1):
                    await interaction.response.send_message(
                        "❌ Für prozentuale Rabatte verwende Werte zwischen 0 und 1 (z.B. 0.10 für 10%)!",
                        ephemeral=True
                    )
                    return
                elif discount_type == "fixed" and discount_value < 0:
                    await interaction.response.send_message(
                        "❌ Feste Rabatte müssen positiv sein!",
                        ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ Ungültiger Rabatt-Wert! Verwende Zahlen (z.B. 0.10 oder 5).",
                    ephemeral=True
                )
                return
            
            try:
                max_uses = int(self.max_uses.value)
                if max_uses < -1 or max_uses == 0:
                    await interaction.response.send_message(
                        "❌ Maximale Nutzungen müssen -1 (unbegrenzt) oder positive Zahl sein!",
                        ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ Ungültiger Wert für maximale Nutzungen!",
                    ephemeral=True
                )
                return
            
            # Load existing codes
            discount_codes = load_discount_codes()
            
            if code in discount_codes:
                await interaction.response.send_message(
                    f"❌ Discount-Code '{code}' existiert bereits!",
                    ephemeral=True
                )
                return
            
            # Create new code
            new_code = {
                "type": discount_type,
                "value": discount_value,
                "max_uses": max_uses,
                "current_uses": 0,
                "used_by": [],
                "auto_delete": False,  # Standard: nicht automatisch löschen
                "created_at": int(datetime.now().timestamp()),
                "description": self.description.value or f"{'Prozentualer' if discount_type == 'percentage' else 'Fester'} Rabatt"
            }
            
            discount_codes[code] = new_code
            save_discount_codes(discount_codes)
            
            # Success message
            if discount_type == "percentage":
                value_display = f"{int(discount_value * 100)}%"
            else:
                value_display = f"{discount_value}€"
            
            usage_display = "unbegrenzt" if max_uses == -1 else f"{max_uses}x"
            
            await interaction.response.send_message(
                f"✅ **Discount-Code erstellt!**\n\n"
                f"🎟️ **Code:** {code}\n"
                f"💰 **Rabatt:** {value_display}\n"
                f"🔢 **Nutzungen:** {usage_display}\n"
                f"📝 **Beschreibung:** {new_code['description']}\n\n"
                f"Der Code ist sofort im Shop verfügbar!",
                ephemeral=True
            )
            print(f"➕ Enhanced Discount Code erstellt: {code} ({value_display}, {usage_display}) von {interaction.user}")
            
        except Exception as e:
            print(f"❌ Fehler beim Erstellen des Enhanced Discount Codes: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

class SingleUseDiscountModal(Modal):
    def __init__(self):
        super().__init__(title="🎫 Einmaligen Discount-Code erstellen")
        
        self.code_name = TextInput(
            label="🎟️ Code-Name",
            placeholder="z.B. WELCOME25, FIRST10...",
            required=True,
            max_length=20,
            min_length=2
        )
        
        self.discount_type = TextInput(
            label="💰 Rabatt-Typ (percentage/fixed)",
            placeholder="percentage = %, fixed = €",
            default="percentage",
            required=True,
            max_length=10
        )
        
        self.discount_value = TextInput(
            label="🔢 Rabatt-Wert",
            placeholder="Für %: 0.25 (=25%), für €: 10 (=10€)",
            required=True,
            max_length=10
        )
        
        self.description = TextInput(
            label="📝 Beschreibung",
            placeholder="z.B. Willkommensrabatt für Neukunden...",
            required=False,
            max_length=100
        )
        
        self.add_item(self.code_name)
        self.add_item(self.discount_type)
        self.add_item(self.discount_value)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate inputs (similar to above but force max_uses = 1)
            code = self.code_name.value.upper().strip()
            discount_type = self.discount_type.value.lower().strip()
            
            if discount_type not in ["percentage", "fixed"]:
                await interaction.response.send_message(
                    "❌ Rabatt-Typ muss 'percentage' oder 'fixed' sein!",
                    ephemeral=True
                )
                return
            
            try:
                discount_value = float(self.discount_value.value)
                if discount_type == "percentage" and (discount_value < 0 or discount_value > 1):
                    await interaction.response.send_message(
                        "❌ Für prozentuale Rabatte verwende Werte zwischen 0 und 1 (z.B. 0.25 für 25%)!",
                        ephemeral=True
                    )
                    return
                elif discount_type == "fixed" and discount_value < 0:
                    await interaction.response.send_message(
                        "❌ Feste Rabatte müssen positiv sein!",
                        ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ Ungültiger Rabatt-Wert! Verwende Zahlen (z.B. 0.25 oder 10).",
                    ephemeral=True
                )
                return
            
            # Load existing codes
            discount_codes = load_discount_codes()
            
            if code in discount_codes:
                await interaction.response.send_message(
                    f"❌ Discount-Code '{code}' existiert bereits!",
                    ephemeral=True
                )
                return
            
            # Create single-use code
            new_code = {
                "type": discount_type,
                "value": discount_value,
                "max_uses": 1,  # Always single use
                "current_uses": 0,
                "used_by": [],
                "auto_delete": False,  # Standard: deaktivieren, nicht löschen
                "created_at": int(datetime.now().timestamp()),
                "description": self.description.value or f"Einmaliger {'prozentualer' if discount_type == 'percentage' else 'fester'} Rabatt"
            }
            
            discount_codes[code] = new_code
            save_discount_codes(discount_codes)
            
            # Success message
            if discount_type == "percentage":
                value_display = f"{int(discount_value * 100)}%"
            else:
                value_display = f"{discount_value}€"
            
            await interaction.response.send_message(
                f"✅ **Einmaliger Discount-Code erstellt!**\n\n"
                f"🎟️ **Code:** {code}\n"
                f"💰 **Rabatt:** {value_display}\n"
                f"🎫 **Nutzungen:** 1x (einmalig)\n"
                f"📝 **Beschreibung:** {new_code['description']}\n\n"
                f"⚠️ **Wichtig:** Dieser Code kann nur einmal verwendet werden und wird danach automatisch deaktiviert!",
                ephemeral=True
            )
            print(f"🎫 Single-Use Discount Code erstellt: {code} ({value_display}) von {interaction.user}")
            
        except Exception as e:
            print(f"❌ Fehler beim Erstellen des Single-Use Discount Codes: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

class ResetDiscountUsageModal(Modal):
    def __init__(self):
        super().__init__(title="🔄 Code-Nutzung zurücksetzen")
        
        self.code_name = TextInput(
            label="🎟️ Code-Name",
            placeholder="Name des Codes zum Zurücksetzen...",
            required=True,
            max_length=20
        )
        
        self.confirmation = TextInput(
            label="⚠️ Bestätigung (schreibe 'RESET')",
            placeholder="Schreibe RESET um zu bestätigen",
            required=True,
            max_length=10
        )
        
        self.add_item(self.code_name)
        self.add_item(self.confirmation)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.confirmation.value.upper() != "RESET":
                await interaction.response.send_message(
                    "❌ Zurücksetzung nicht bestätigt. Schreibe 'RESET' um zu bestätigen.",
                    ephemeral=True
                )
                return
            
            code = self.code_name.value.upper().strip()
            discount_codes = load_discount_codes()
            
            if code not in discount_codes:
                await interaction.response.send_message(
                    f"❌ Code '{code}' nicht gefunden!\n\n"
                    f"Überprüfe die Schreibweise des Codes.",
                    ephemeral=True
                )
                return
            
            # Store old values for confirmation
            old_uses = discount_codes[code].get("current_uses", 0)
            old_users = len(discount_codes[code].get("used_by", []))
            
            # Reset usage
            discount_codes[code]["current_uses"] = 0
            discount_codes[code]["used_by"] = []
            
            save_discount_codes(discount_codes)
            
            await interaction.response.send_message(
                f"✅ **Code-Nutzung zurückgesetzt!**\n\n"
                f"🎟️ **Code:** {code}\n"
                f"🔄 **Vorherige Nutzungen:** {old_uses}\n"
                f"👥 **Vorherige Nutzer:** {old_users}\n\n"
                f"Der Code kann jetzt wieder von allen Nutzern verwendet werden!",
                ephemeral=True
            )
            print(f"🔄 Discount Code Nutzung zurückgesetzt: {code} (war {old_uses}x verwendet) von {interaction.user}")
            
        except Exception as e:
            print(f"❌ Fehler beim Zurücksetzen der Code-Nutzung: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

async def show_banner_config(interaction):
    """Banner configuration and management"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Administrator-Rechte erforderlich.", ephemeral=True)
        return
    
    current_banner = get_server_banner_url(interaction.guild.id)
    
    embed = discord.Embed(
        title="🖼️ Banner Konfiguration",
        description="Verwalte das Banner für alle Bot-Nachrichten:",
        color=0xe74c3c
    )
    
    embed.add_field(
        name="📄 Aktuelles Banner",
        value=f"```{current_banner}```",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Banner ändern",
        value="**Methode 1:** Poste einfach ein Bild in diesen Chat! Als Admin wird es automatisch als neues Banner gesetzt.\n\n"
              "**Methode 2:** Nutze den Button unten für manuelle URL-Eingabe.\n\n"
              "**Unterstützte Formate:** PNG, JPG, JPEG, GIF, WEBP",
        inline=False
    )
    
    # Set current banner as preview
    if current_banner.startswith("http"):
        embed.set_image(url=current_banner)
    
    banner_view = View(timeout=300)
    
    # Manual URL button
    manual_button = Button(label="🔗 URL eingeben", style=discord.ButtonStyle.primary)
    manual_button.callback = lambda i: show_banner_url_modal(i)
    
    # Reset to default button  
    reset_button = Button(label="↩️ Standard wiederherstellen", style=discord.ButtonStyle.secondary)
    reset_button.callback = lambda i: reset_banner_to_default(i)
    
    # Back button
    back_button = Button(label="⬅️ Zurück", style=discord.ButtonStyle.danger)
    back_button.callback = lambda i: show_branding_config(i)
    
    banner_view.add_item(manual_button)
    banner_view.add_item(reset_button)
    banner_view.add_item(back_button)
    
    await interaction.response.send_message(embed=embed, view=banner_view, ephemeral=True)

async def show_banner_url_modal(interaction):
    """Show modal for manual banner URL input"""
    modal = BannerUrlModal()
    await interaction.response.send_modal(modal)

async def reset_banner_to_default(interaction):
    """Reset banner to default"""
    try:
        default_banner = "attached_assets/bannergif-ezgif.com-video-to-gif-converter_1757170618892.gif"
        set_server_banner_url(interaction.guild.id, default_banner)
        
        await interaction.response.send_message(
            "✅ **Banner zurückgesetzt!**\n\n"
            "Das Standard-Banner wird wieder für alle Bot-Nachrichten verwendet.",
            ephemeral=True
        )
        print(f"🖼️ Banner reset to default for guild {interaction.guild.name}")
        
    except Exception as e:
        print(f"❌ Error resetting banner: {e}")
        await interaction.response.send_message(
            "❌ Fehler beim Zurücksetzen des Banners.",
            ephemeral=True
        )

class BannerUrlModal(Modal):
    def __init__(self):
        super().__init__(title="🖼️ Banner URL eingeben")
        
        self.banner_url = TextInput(
            label="🔗 Banner URL",
            placeholder="https://example.com/banner.png oder lokaler Pfad...",
            required=True,
            max_length=500
        )
        
        self.add_item(self.banner_url)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            banner_url = self.banner_url.value.strip()
            
            # Basic URL validation
            if not (banner_url.startswith("http") or banner_url.startswith("attached_assets/")):
                await interaction.response.send_message(
                    "❌ Ungültige URL! Verwende eine HTTP(S)-URL oder einen lokalen Pfad (attached_assets/...).",
                    ephemeral=True
                )
                return
            
            # Set new banner
            set_server_banner_url(interaction.guild.id, banner_url)
            
            # Confirmation embed
            embed = discord.Embed(
                title="✅ Banner aktualisiert!",
                description=f"Das neue Banner wurde erfolgreich gesetzt:\n\n`{banner_url}`\n\nDas Banner wird ab sofort in allen Bot-Nachrichten verwendet!",
                color=0x00ff00
            )
            
            # Try to preview the banner
            if banner_url.startswith("http"):
                embed.set_image(url=banner_url)
                
            embed.set_footer(text="Haze Visuals • Banner System")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            print(f"🖼️ Banner manually set for guild {interaction.guild.name}: {banner_url}")
            
        except Exception as e:
            print(f"❌ Error setting banner URL: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Setzen der Banner-URL.",
                ephemeral=True
            )

class AutoDeleteDiscountModal(Modal):
    def __init__(self):
        super().__init__(title="🗑️ Auto-Lösch-Code erstellen")
        
        self.code_name = TextInput(
            label="🎟️ Code-Name",
            placeholder="z.B. WELCOME50, FLASH24...",
            required=True,
            max_length=20,
            min_length=2
        )
        
        self.discount_type = TextInput(
            label="💰 Rabatt-Typ (percentage/fixed)",
            placeholder="percentage = %, fixed = €",
            default="percentage",
            required=True,
            max_length=10
        )
        
        self.discount_value = TextInput(
            label="🔢 Rabatt-Wert",
            placeholder="Für %: 0.50 (=50%), für €: 15 (=15€)",
            required=True,
            max_length=10
        )
        
        self.description = TextInput(
            label="📝 Beschreibung",
            placeholder="z.B. Flash-Sale Code - löscht sich automatisch...",
            required=False,
            max_length=100
        )
        
        self.add_item(self.code_name)
        self.add_item(self.discount_type)
        self.add_item(self.discount_value)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate inputs
            code = self.code_name.value.upper().strip()
            discount_type = self.discount_type.value.lower().strip()
            
            if discount_type not in ["percentage", "fixed"]:
                await interaction.response.send_message(
                    "❌ Rabatt-Typ muss 'percentage' oder 'fixed' sein!",
                    ephemeral=True
                )
                return
            
            try:
                discount_value = float(self.discount_value.value)
                if discount_type == "percentage" and (discount_value < 0 or discount_value > 1):
                    await interaction.response.send_message(
                        "❌ Für prozentuale Rabatte verwende Werte zwischen 0 und 1 (z.B. 0.50 für 50%)!",
                        ephemeral=True
                    )
                    return
                elif discount_type == "fixed" and discount_value < 0:
                    await interaction.response.send_message(
                        "❌ Feste Rabatte müssen positiv sein!",
                        ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ Ungültiger Rabatt-Wert! Verwende Zahlen (z.B. 0.50 oder 15).",
                    ephemeral=True
                )
                return
            
            # Load existing codes
            discount_codes = load_discount_codes()
            
            if code in discount_codes:
                await interaction.response.send_message(
                    f"❌ Discount-Code '{code}' existiert bereits!",
                    ephemeral=True
                )
                return
            
            # Create auto-delete code (always single use + auto delete)
            new_code = {
                "type": discount_type,
                "value": discount_value,
                "max_uses": 1,  # Always single use for auto-delete
                "current_uses": 0,
                "used_by": [],
                "auto_delete": True,  # Auto-delete enabled
                "created_at": int(datetime.now().timestamp()),
                "description": self.description.value or f"Auto-Lösch {'prozentualer' if discount_type == 'percentage' else 'fester'} Rabatt"
            }
            
            discount_codes[code] = new_code
            save_discount_codes(discount_codes)
            
            # Success message
            if discount_type == "percentage":
                value_display = f"{int(discount_value * 100)}%"
            else:
                value_display = f"{discount_value}€"
            
            await interaction.response.send_message(
                f"✅ **Auto-Lösch-Code erstellt!**\n\n"
                f"🎟️ **Code:** {code}\n"
                f"💰 **Rabatt:** {value_display}\n"
                f"🗑️ **Verhalten:** Löscht sich automatisch nach der ersten Verwendung\n"
                f"📝 **Beschreibung:** {new_code['description']}\n\n"
                f"⚠️ **Wichtig:** Dieser Code verschwindet komplett nach einmaliger Nutzung!",
                ephemeral=True
            )
            print(f"🗑️ Auto-Delete Discount Code erstellt: {code} ({value_display}) von {interaction.user}")
            
        except Exception as e:
            print(f"❌ Fehler beim Erstellen des Auto-Delete Discount Codes: {e}")
            await interaction.response.send_message(
                "❌ Ein Fehler ist aufgetreten.",
                ephemeral=True
            )

def run_flask():
    """Run Flask server in a separate thread"""
    app.run(host="0.0.0.0", port=5000, debug=False)

def run_discord_bot():
    """Run Discord bot"""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ Fehler: DISCORD_TOKEN Umgebungsvariable ist nicht gesetzt!")
        exit(1)
    
    bot.run(token)

# Bot starten
if __name__ == "__main__":
    print("🚀 Starting Discord bot with HTTP server...")
    
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ HTTP server started on port 5000")
    
    # Start Discord bot (this will block)
    run_discord_bot()