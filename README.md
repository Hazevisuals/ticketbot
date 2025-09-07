# 🌪️ Haze Visuals Discord Bot

Ein umfassender Discord-Bot für Haze Visuals mit vollständigem Ticket-System, Clothing-Bestellungen, Payment-Processing mit 8 verschiedenen Zahlungsmethoden, Staff-Management, Auto-Update-Funktionen, Review-System, Giveaway-Funktionalität und Member-Counting.

## ✨ Features

### 🎫 Ticket System
- Multi-Kategorie Tickets (Bestellung, Support, Bug Report, Vorschlag, Bewerbung)
- Automatische Kanal-Erstellung und -Verwaltung
- Ticket-Status-Verfolgung mit Workflow-Management
- Echtzeit Ticket-Counter

### 👕 Clothing Order System
- Streamlined 3-Option System (Custom, Finished, Fragen)
- Multi-Step Workflow mit Farb- und Produktauswahl
- Dynamische Preisberechnung mit Rabattcodes
- Lieferoptionen (Standard, Fast +25%, Extra Fast +50%)

### 💳 Payment Integration
- 8 verschiedene Zahlungsmethoden
- PayPal Integration (hazeevisuals@gmail.com)
- Paysafecard, Bank Transfer Support
- Automatische Team-Benachrichtigungen

### ⚙️ Admin Panel
- Vollständig anpassbares Konfigurationspanel
- Server-spezifische Einstellungen
- Branding-Anpassungen
- Rollen- und Kanal-Management

### 🏆 Giveaway System
- Automatische Kanal-Erstellung
- Live-Countdown Timer
- Gewinner-Auswahl mit DM-Benachrichtigungen
- Winner-Channel Integration

### ⭐ Review System
- 1-5 Sterne Bewertungssystem
- Automatische Veröffentlichung in Review-Channel
- Customer Feedback Management

### 👥 Member Counter
- Live Member-Counter Voice Channel
- Automatische Updates bei Join/Leave
- Rate-Limiting für API-Schonung

## 🚀 Installation

### Voraussetzungen
- Python 3.11+
- Discord Bot Token
- 256 MB RAM minimum (512 MB empfohlen)

### Dependencies installieren
```bash
pip install -r requirements.txt
```

### Environment Variables
```bash
DISCORD_TOKEN=your_discord_bot_token_here
PORT=5000
```

### Bot starten
```bash
python start.py
```

## 📁 Dateistruktur

```
├── main.py                 # Haupt-Bot-Code
├── start.py                # Optimierter Startup-Script
├── requirements.txt        # Python Dependencies
├── Procfile               # Process-Konfiguration
├── runtime.txt            # Python Version
├── prices.json            # Produktpreise
├── server_configs.json    # Server-Konfigurationen
├── appointments.json      # Termine-System
├── discount_codes.json    # Rabattcodes
├── pending_tickets.json   # Ticket-System
└── attached_assets/       # Banner und Assets
```

## 🌐 Hosting

### Unterstützte Plattformen
- **Heroku** - Einfaches Git-Deployment
- **Railway** - Auto-Deploy via GitHub
- **DigitalOcean App Platform** - Automatisches Scaling
- **VPS/Dedicated Server** - Manuelle Installation

### Deployment-Befehle
```bash
# Heroku
git push heroku main

# VPS
python start.py
```

## 🔧 Konfiguration

### Slash Commands
- `/admin` - Umfassendes Admin-Konfigurationspanel
- `/preise` - Zeigt Preisliste an
- `/ticket_panel` - Erstellt Ticket-Panel
- `/giveaway` - Erstellt Giveaway mit Countdown
- `/setup` - Bot Setup für neue Server

### Rollen-Berechtigungen
- **Administrator** - Vollzugriff auf alle Funktionen
- **HV | Team** - Staff-Funktionen
- **HV | Leitung** - Management-Funktionen

## 📊 System Requirements

- **RAM:** 256 MB minimum, 512 MB empfohlen
- **CPU:** 1 vCPU ausreichend
- **Storage:** 100 MB minimum
- **Bandwidth:** Niedrig, abhängig von Server-Aktivität

## 🛡️ Sicherheit

- Environment Variables für sensible Daten
- Rollen-basierte Zugriffskontrolle
- Sichere Payment-Integration
- Automatisches Error-Logging

## 📞 Support

Bei Fragen oder Problemen wende dich an das Haze Visuals Team.

---

**Entwickelt für Haze Visuals** | **Discord Bot Version 2.5.0**