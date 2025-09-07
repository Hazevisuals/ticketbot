#!/usr/bin/env python3
"""
Haze Visuals Discord Bot - Startup Script
Optimized for external hosting platforms
"""

import os
import sys
import asyncio
import signal
import logging
from main import bot, app
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('HazeVisuals')

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    # Close bot connection
    asyncio.create_task(bot.close())
    sys.exit(0)

def run_flask_server():
    """Run Flask server in separate thread"""
    try:
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
    except Exception as e:
        logger.error(f"Flask server error: {e}")

async def main():
    """Main startup function"""
    # Check for Discord token
    discord_token = os.environ.get('DISCORD_TOKEN')
    if not discord_token:
        logger.error("❌ DISCORD_TOKEN environment variable not found!")
        logger.error("Please set your Discord bot token in the environment variables.")
        sys.exit(1)
    
    logger.info("🚀 Starting Haze Visuals Discord Bot...")
    logger.info(f"🐍 Python version: {sys.version}")
    logger.info(f"📍 Working directory: {os.getcwd()}")
    
    try:
        # Start Flask server in background thread
        flask_thread = threading.Thread(target=run_flask_server, daemon=True)
        flask_thread.start()
        logger.info("✅ HTTP server started in background")
        
        # Start Discord bot
        await bot.start(discord_token)
        
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        raise
    finally:
        if not bot.is_closed():
            await bot.close()
        logger.info("🛑 Bot shutdown complete")

if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutdown completed")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        sys.exit(1)