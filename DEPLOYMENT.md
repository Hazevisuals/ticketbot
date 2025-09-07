# 🚀 Haze Visuals Discord Bot - Deployment Guide

## 📋 Required Files for Deployment

Upload these files to your Discord bot hosting platform:

### Core Files:
- `main.py` - Main bot application
- `start.py` - Optimized startup script
- `requirements.txt` - Python dependencies
- `Procfile` - Process configuration (for Heroku/Railway)
- `runtime.txt` - Python version specification

### Data Files:
- `prices.json` - Product pricing data
- `server_configs.json` - Server configurations
- `appointments.json` - Appointment system data
- `discount_codes.json` - Discount codes database
- `pending_tickets.json` - Ticket system data

### Optional Files:
- `attached_assets/` - Banner images (if needed)

## 🔧 Environment Variables

Set these environment variables on your hosting platform:

```bash
DISCORD_TOKEN=your_discord_bot_token_here
PORT=5000
```

## 🌐 Supported Hosting Platforms

### Heroku:
1. Create new app
2. Upload files via Git or ZIP
3. Set environment variables in Settings > Config Vars
4. Deploy with `git push heroku main`

### Railway:
1. Create new project
2. Connect GitHub repo or upload files
3. Set environment variables in Variables tab
4. Deploy automatically

### DigitalOcean App Platform:
1. Create new app
2. Upload files or connect GitHub
3. Set environment variables
4. Deploy with automatic scaling

### VPS/Dedicated Server:
1. Upload files to server
2. Install Python 3.11+
3. Run: `pip install -r requirements.txt`
4. Set environment variables
5. Start with: `python start.py`

## 📊 Resource Requirements

- **RAM:** 256 MB minimum, 512 MB recommended
- **CPU:** 1 vCPU sufficient for most servers
- **Storage:** 100 MB minimum
- **Bandwidth:** Low usage, depends on server activity

## 🔒 Security Notes

- Never commit your DISCORD_TOKEN to version control
- Use environment variables for all sensitive data
- Regularly update dependencies for security patches

## 🆘 Support

Bot includes automatic error handling and logging for easy troubleshooting on any platform.