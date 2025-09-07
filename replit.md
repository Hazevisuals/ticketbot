# Overview

A comprehensive Discord bot for the Haze Visuals business that manages custom design services including pricing displays, administrative tools, advanced ticket management, automated order workflows with step-by-step polls, payment processing integration, and a complete customer review system. The bot serves German-speaking customers with professional business automation.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Updates

## Enhanced Discount Code System (September 2025)
- **Einmalig nutzbare Discount Codes**: Codes können jetzt auf 1x Nutzung limitiert werden und deaktivieren sich automatisch
- **Prozentuale und feste Geldbeträge**: Unterstützung für sowohl % (z.B. 0.10 = 10%) als auch feste Euro-Beträge (z.B. 5€)
- **Shop-Ticket Integration**: Kunden können direkt im Shop-Ticket Rabattcodes eingeben mit "🎟️ Discount-Code eingeben" Button
- **Erweiterte Admin-Verwaltung**: Neue Admin-Panel-Optionen für Code-Erstellung, einmalige Codes und Nutzungsreset
- **Automatische Migration**: Bestehende Codes werden automatisch ins neue Format migriert

## Custom Banner System (September 2025)
- **Server Owner Banner Upload**: Admins/Owner können durch einfaches Posten eines Bildes das Bot-Banner ändern
- **Automatische Erkennung**: System erkennt automatisch Bildanhänge von berechtigten Nutzern und setzt sie als Banner
- **Admin Panel Integration**: Banner-Verwaltung im Admin-Panel mit manueller URL-Eingabe und Zurücksetzen-Funktion
- **Unterstützte Formate**: PNG, JPG, JPEG, GIF, WEBP für maximale Flexibilität
- **Zentrale Banner-Verwaltung**: Alle Bot-Embeds verwenden automatisch das konfigurierte Server-Banner

# System Architecture

## Bot Framework
- **Discord.py Library**: Uses the modern discord.py library with application commands (slash commands) and UI components
- **Command System**: Implements Discord's slash command system for better user experience and discoverability
- **Interactive UI**: Advanced View and Button components with modals, polls, and multi-step workflows
- **Business Automation**: Complete order management from ticket creation to payment processing and customer reviews

## Data Management
- **JSON File Storage**: Pricing data persists in prices.json file for data retention across restarts
- **Dynamic Data Model**: Pricing information is editable via secure admin commands
- **Persistent Configuration**: Bot settings and pricing configurations survive bot restarts
- **Business Integration**: Supports payment methods (PayPal: hazeevisuals@gmail.com, Tebex: https://www.hazevisuals.shop)

## User Interface Design
- **Category-Based Navigation**: Pricing information organized into distinct categories with interactive buttons
- **Professional Ticket System**: Multi-category ticket creation (Bestellung, Support, Bug Report, Vorschlag, Bewerbung)
- **Streamlined Clothing Orders**: Three-option system (Custom, Finished, Fragen) for simplified order management
- **Custom Order Workflow**: Multi-step process with color selection, product choice, discount codes, and delivery options
- **Dynamic Pricing System**: Real-time price calculation with discount codes (FIJI, CATLEEN, STILLES - 10% off)
- **Delivery Options**: Standard, Fast delivery (+25%), Extra fast delivery (+50%) with automated price calculation
- **Workflow Management**: Ticket status progression (Created → Claimed → Paid → Finished → Review)
- **Customer Review System**: 1-5 star rating system with optional comments posted to dedicated review channel
- **Real-time Ticket Counter**: Private voice channel displaying current open ticket count in real-time
- **Comprehensive Giveaway System**: Complete giveaway management with automatic channel creation, countdown timers, and winner selection
- **German Language**: All user-facing text in German for target market

## Error Handling
- **Environment Variable Validation**: Checks for required Discord token before attempting to start
- **Graceful Failure**: Exits cleanly with error message if token is missing

## Architecture Benefits
- **Simple Deployment**: Single-file application with minimal dependencies
- **Low Resource Usage**: No database overhead, minimal memory footprint
- **Fast Response Times**: In-memory data access provides instant responses
- **Easy Maintenance**: Straightforward code structure for quick updates

## Advanced Features
- **Role-Based Security**: HV | Team and HV | Leitung role permissions for administrative functions
- **Payment Integration**: Multiple payment methods (PayPal: hazeevisuals@gmail.com, Paysafecard, Bank Transfer with team notifications)
- **Product Catalog**: Custom Paket (20€), Fertiges Paket (10€), Custom einzeln (5€), Custom Weste (10€)
- **Discount System**: Automated code validation and price calculation for promotional codes
- **Team Notifications**: Automatic role pings for bank transfer requests and support needs
- **Category Management**: Uses specific Discord category IDs for organized ticket workflow
- **Automated Channel Management**: Dynamic ticket channel creation, renaming, and moving between categories
- **Review Publishing**: Customer reviews automatically posted to public review channel (1413668548399726602)
- **Business Analytics**: Complete order tracking from creation to completion with timestamps
- **Professional Branding**: Haze Visuals banner integration on all ticket messages and panels
- **Giveaway Management**: Automatic channel creation, participant tracking, countdown system, and winner announcements
- **Winner Notifications**: Automatic DM to winners and public announcements in dedicated winner channels

# External Dependencies

## Core Dependencies
- **Discord.py**: Python library for Discord bot development and API interaction
- **Python Standard Library**: Uses `os`, `json`, `datetime`, `random` modules for environment variables, data storage, time management, and giveaway winner selection
- **External APIs**: CoinGecko API for real-time cryptocurrency pricing
- **Flask**: HTTP server for webhook handling and health checks

## Runtime Requirements
- **Discord Bot Token**: Requires `DISCORD_TOKEN` environment variable for authentication
- **Discord Application**: Bot must be registered in Discord Developer Portal with appropriate permissions

## Deployment Environment
- **Python Runtime**: Requires Python environment with discord.py package installed
- **Environment Variables**: Depends on system environment variable configuration for secure token storage