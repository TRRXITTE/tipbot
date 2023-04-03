import os
import random
import string
import logging
from configparser import ConfigParser
from datetime import datetime, timedelta
from decimal import Decimal
import json

from telegram import Update, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters

import mysql.connector
from web3 import Web3, HTTPProvider

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

# Load configuration
config = ConfigParser()
config.read('config.ini')

# Load Telegram API token from configuration
TELEGRAM_TOKEN = config.get('Telegram', 'token')

# Load BEP20 contract address and deposit address from configuration
BEP20_CONTRACT_ADDRESS = config.get('BEP20', 'contract_address')
BEP20_DEPOSIT_ADDRESS = config.get('BEP20', 'deposit_address')

# Load MariaDB configuration
DB_HOST = config.get('Database', 'host')
DB_PORT = config.get('Database', 'port')
DB_NAME = config.get('Database', 'database')
DB_USER = config.get('Database', 'user')
DB_PASSWORD = config.get('Database', 'password')

# Load private key securely
private_key = os.environ.get('PRIVATE_KEY')
if private_key is None:
    logger.error('PRIVATE_KEY environment variable not set')
    exit(1)

# Initialize Web3
logger.info('Initializing Web3...')
web3 = Web3(HTTPProvider('https://bsc-dataseed1.binance.org/'))
logger.info('Web3 initialized.')

# Load BEP20 contract ABI
logger.info('Loading BEP20 contract ABI...')
with open('abi.json', 'r') as f:
    abi = json.load(f)
logger.info('BEP20 contract ABI loaded.')

# Convert BEP20_CONTRACT_ADDRESS to checksum address
logger.info('Converting BEP20 contract address to checksum address...')
BEP20_CONTRACT_ADDRESS = web3.toChecksumAddress(BEP20_CONTRACT_ADDRESS)
logger.info('BEP20 contract address converted to checksum address.')

# Initialize BEP20 contract
logger.info('Initializing BEP20 contract...')
contract = web3.eth.contract(address=BEP20_CONTRACT_ADDRESS, abi=abi)
logger.info('BEP20 contract initialized.')

# Initialize MySQL connection
logger.info('Initializing MySQL connection...')
db = mysql.connector.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)
cursor = db.cursor()
logger.info('MySQL connection initialized.')

# Set up random string generator for generating user addresses
def generate_random_string(length):
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(length))

# Define command handlers

def start(update: Update, context: CallbackContext):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi there! I am a BEP20 tip bot. Use /help to see available commands.')

def help(update: Update, context: CallbackContext):
    """Send a message when the command /help is issued."""
    help_text = '''Available commands:
    
/deposit - Get your deposit address.
/withdraw <address> <amount> - Withdraw tokens to an external address.
/balance - Get your token balance.
/tip <amount> <username> - Send tokens to another user.
/rain <amount> - Send tokens to all active users in the chat.
/draw <amount> <num_winners> <hashtag> - Start a giveaway and randomly reward users who reply with the specified hashtag.
/help - Show this help message.'''
    update.message.reply_text(help_text)

def deposit(update: Update, context: CallbackContext):
    """Generate a deposit address for the user."""
    user_id = update.message.from_user.id
    address = generate_random_string(32)
    cursor.execute('INSERT INTO addresses (user_id, address) VALUES (%s, %s)', (user_id, address))
    db.commit()
    update.message.reply_text(f'Your deposit address is: {address}\n\nPlease use this address to deposit BNB for transaction fees.')


def myaddress(update: Update, context: CallbackContext):
    """Show the user's deposit address."""
    user_id = update.message.from_user.id
    cursor.execute('SELECT address FROM addresses WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    if result is None:
        update.message.reply_text('You do not have a deposit address yet. Use /deposit to generate one.')
    else:
        address = result[0]
        update.message.reply_text(f'Your deposit address is: {address}\n\nPlease use this address to deposit BNB for transaction fees.')

def withdraw(update: Update, context: CallbackContext):
    """Withdraw tokens to an external address."""
    user_id = update.message.from_user.id
    args = context.args
    if len(args) != 2:
        update.message.reply_text('Usage: /withdraw <address> <amount>')
        return
    address = args[0]
    amount = Decimal(args[1])
    if amount < 1000:
        update.message.reply_text('Minimum withdrawal amount is 1000 tokens.')
        return
    cursor.execute('SELECT balance FROM balances WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    if result is None:
        update.message.reply_text('You do not have any tokens to withdraw.')
        return
    balance = Decimal(result[0])
    if balance < amount:
        update.message.reply_text('Insufficient balance.')
        return
    # Transfer tokens to external address
    tx_hash = contract.functions.transfer(address, amount).transact({'from': BEP20_DEPOSIT_ADDRESS, 'gas': 100000})
    # Update balance in database
    cursor.execute('UPDATE balances SET balance = balance - %s WHERE user_id = %s', (amount, user_id))
    db.commit()
    update.message.reply_text(f'Transaction sent: https://bscscan.com/tx/{tx_hash.hex()}')
