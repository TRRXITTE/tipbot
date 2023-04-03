import os
import getpass
import random
import string
import logging
from configparser import ConfigParser
from datetime import datetime, timedelta
from decimal import Decimal
import json
import uuid

from telegram import Update, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters

import mysql.connector
from web3 import Web3, HTTPProvider, Account

from eth_utils import to_checksum_address

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
NYANTE_CONTRACT_ADDRESS = config.get('NYANTE', 'contract_address')
NYANTE_DEPOSIT_ADDRESS = config.get('NYANTE', 'deposit_address')

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
NYANTE_CONTRACT_ADDRESS = web3.toChecksumAddress(NYANTE_CONTRACT_ADDRESS)
logger.info('BEP20 contract address converted to checksum address.')

# Initialize BEP20 contract
logger.info('Initializing BEP20 contract...')
nyante_contract = web3.eth.contract(address=NYANTE_CONTRACT_ADDRESS, abi=abi)
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
    update.message.reply_text('Hi there! I am a Nyantereum International tip bot. Use /help to see available commands.')

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
    if update.message.chat.type == 'private':
        cursor.execute('SELECT address, private_key FROM addresses WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        if result is None:
            # Generate new address and private key
            account = web3.eth.account.create()
            address = account.address
            private_key = account.privateKey.hex()
            # Check if address is valid
            if not web3.isAddress(address):
                update.message.reply_text('Error: Invalid deposit address generated. Please try again.')
                return
            # Insert new address into database
            cursor.execute('INSERT INTO addresses (user_id, address, private_key) VALUES (%s, %s, %s)', (user_id, address, private_key))
            db.commit()
        else:
            address = result[0]
            private_key = result[1]
        # Get balance of NYANTE contract
        nyante_balance = nyante_contract.functions.balanceOf(NYANTE_DEPOSIT_ADDRESS).call()
        message = f'Your deposit address is: {address}\n\nPlease use this address to deposit Nyantereum International for transfer.\n\nThe current balance of NYANTE tokens is: \nAmount: {nyante_balance} \nNyantereum International'
        update.message.reply_text(message)
        context.bot.send_message(chat_id=user_id, text=message)
    else:
        update.message.reply_text('This command can only be used in a private chat.')

def privkey(update: Update, context: CallbackContext):
    """Send the user's private key and address in a direct message."""
    user_id = update.message.from_user.id
    if user_id != ADMIN_USER_ID:
        update.message.reply_text('You are not authorized to use this command.')
        return
    account = web3.eth.account.privateKeyToAccount(private_key)
    address = to_checksum_address(account.address)
    update.message.reply_text(f'Your private key is:\n{private_key}\n\nYour address is:\n{address}', quote=False)
    context.bot.send_message(chat_id=user_id, text='Please keep your private key and address safe and do not share them with anyone.', quote=False)

def balance(update: Update, context: CallbackContext):
    """Get the user's token balance."""
    user_id = update.message.from_user.id
    cursor.execute('SELECT balance FROM balances WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    if result is None:
        update.message.reply_text('You do not have any tokens.')
    else:
        balance = Decimal(result[0])
        update.message.reply_text(f'Your balance is: {balance} tokens.')

def myaddress(update: Update, context: CallbackContext):
    """Show the user's deposit address and balance."""
    user_id = update.message.from_user.id
    cursor.execute('SELECT address, balance FROM addresses JOIN balances ON addresses.user_id = balances.user_id WHERE addresses.user_id = %s', (user_id,))
    result = cursor.fetchone()
    if result is None:
        update.message.reply_text('You do not have a deposit address yet. Use /deposit to generate one.')
    else:
        address = result[0]
        balance = Decimal(result[1])
        update.message.reply_text(f'Your deposit address is: {address}\n\nPlease use this address to deposit BNB for transaction fees.\n\nYour balance is: {balance} tokens.')

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
    # Estimate gas cost of transaction
    gas_price = web3.eth.gas_price
    gas_limit = web3.eth.estimateGas({
        'from': BEP20_DEPOSIT_ADDRESS,
        'to': address,
        'value': 0,
        'data': nyante_contract.encodeABI(fn_name='transfer', args=[address, amount])
    })
    fee = gas_price * gas_limit
    # Check if user has enough BNB for fee
    cursor.execute('SELECT balance FROM balances WHERE user_id = %s AND address = %s', (user_id, BNB_DEPOSIT_ADDRESS))
    result = cursor.fetchone()
    if result is None:
        update.message.reply_text('You do not have any BNB to pay for the transaction fee.')
        return
    bnb_balance = Decimal(result[0])
    if bnb_balance < fee:
        update.message.reply_text('Insufficient BNB balance to pay for the transaction fee.')
        return
    # Load private key securely
    private_key = os.environ.get('PRIVATE_KEY')
    if private_key is None:
        private_key = getpass.getpass('Enter BNB private key: ')
    account = Account.from_key(private_key)
    # Create unsigned transaction
    nonce = web3.eth.getTransactionCount(account.address)
    tx = {
        'nonce': nonce,
        'gasPrice': gas_price,
        'gas': gas_limit,
        'to': address,
        'value': 0,
        'data': b'',
    }
    # Sign transaction with account
    signed_tx = account.sign_transaction(tx)
    # Send signed transaction
    tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)
    # Deduct fee from BNB balance
    cursor.execute('UPDATE balances SET balance = balance - %s WHERE user_id = %s AND address = %s', (fee, user_id, BNB_DEPOSIT_ADDRESS))
    # Update balance in database
    cursor.execute('UPDATE balances SET balance = balance - %s WHERE user_id = %s', (amount, user_id))
    db.commit()
    update.message.reply_text(f'Transaction sent: https://bscscan.com/tx/{tx_hash.hex()}')

def tip(update: Update, context: CallbackContext):
    """Tip another user with tokens."""
    user_id = update.message.from_user.id
    args = context.args
    if len(args) != 2:
        update.message.reply_text('Usage: /tip <user> <amount>')
        return
    target_user = args[0]
    amount = Decimal(args[1])
    if amount < 1:
        update.message.reply_text('Minimum tip amount is 1 token.')
        return
    cursor.execute('SELECT balance FROM balances WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    if result is None:
        update.message.reply_text('You do not have any tokens to tip.')
        return
    balance = Decimal(result[0])
    if balance < amount:
        update.message.reply_text('Insufficient balance.')
        return
    # Get target user's user_id
    cursor.execute('SELECT user_id FROM users WHERE username = %s', (target_user,))
    result = cursor.fetchone()
    if result is None:
        update.message.reply_text(f'User {target_user} not found.')
        return
    target_user_id = result[0]
    # Update balances in database
    cursor.execute('UPDATE balances SET balance = balance + %s WHERE user_id = %s', (amount, target_user_id))
    cursor.execute('UPDATE balances SET balance = balance - %s WHERE user_id = %s', (amount, user_id))
    db.commit()
    update.message.reply_text(f'You tipped {target_user} {amount} tokens.')

def rain(update: Update, context: CallbackContext):
    """Distribute tokens to a group of users."""
    user_id = update.message.from_user.id
    args = context.args
    if len(args) != 2:
        update.message.reply_text('Usage: /rain <group> <amount>')
        return
    group = args[0]
    amount = Decimal(args[1])
    if amount < 1:
        update.message.reply_text('Minimum rain amount is 1 token.')
        return
    cursor.execute('SELECT balance FROM balances WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    if result is None:
        update.message.reply_text('You do not have any tokens to rain.')
        return
    balance = Decimal(result[0])
    if balance < amount:
        update.message.reply_text('Insufficient balance.')
        return
    # Get list of users in group
    cursor.execute('SELECT user_id FROM users WHERE "group" = %s', (group,))
    results = cursor.fetchall()
    if len(results) == 0:
        update.message.reply_text(f'Group {group} not found.')
        return
    # Calculate amount to distribute to each user
    num_users = len(results)
    amount_per_user = amount / num_users
    # Update balances in database
    for result in results:
        user_id = result[0]
        cursor.execute('UPDATE balances SET balance = balance + %s WHERE user_id = %s', (amount_per_user, user_id))
    cursor.execute('UPDATE balances SET balance = balance - %s WHERE user_id = %s', (amount, user_id))
    db.commit()
    update.message.reply_text(f'You rained {amount} tokens on {num_users} users in group {group}.')

def draw(update: Update, context: CallbackContext):
    """Participate in a draw and have a chance to win tokens."""
    user_id = update.message.from_user.id
    args = context.args
    if len(args) != 3:
        update.message.reply_text('Usage: /draw <amount> <hashtag> <message>')
        return
    amount = Decimal(args[0])
    if amount < 1:
        update.message.reply_text('Minimum draw amount is 1 token.')
        return
    hashtag = args[1]
    message = args[2]
    num_participants = 0
    if update.message.reply_to_message is not None:
        # Check if there are any participants
        cursor.execute('SELECT COUNT(*) FROM draw_entries WHERE round = %s', (current_round,))
        result = cursor.fetchone()
        if result[0] == 0:
            update.message.reply_text('No participants in this round.')
            return
        # Get list of users who replied with the hashtag
        participants = []
        for message in update.message.reply_to_message.reply_markup.inline_keyboard[0]:
            if message.text == hashtag:
                participants.append(message.user.id)
        num_participants = len(participants)
        if num_participants == 0:
            update.message.reply_text(f'No participants with hashtag {hashtag}.')
            return
        # Calculate amount to distribute to each participant
        amount_per_participant = amount / num_participants
        # Update balances in database
        for participant in participants:
            cursor.execute('UPDATE balances SET balance = balance + %s WHERE user_id = %s', (amount_per_participant, participant))
        cursor.execute('UPDATE balances SET balance = balance - %s WHERE user_id = %s', (amount, user_id))
        db.commit()
        update.message.reply_text(f'{num_participants} participants entered the draw with {hashtag}. Each participant won {amount_per_participant} tokens. Message: {message}')
    else:
        # Add entry to draw_entries table
        cursor.execute('INSERT INTO draw_entries (user_id, round, amount) VALUES (%s, %s, %s)', (user_id, current_round, amount))
        db.commit()
        update.message.reply_text(f'You have entered the draw with {amount} tokens. Hashtag: {hashtag}. Message: {message}')

# Initialize the Telegram bot
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)

# Get the dispatcher to register handlers
dispatcher = updater.dispatcher

# Add command handlers
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('help', help))
dispatcher.add_handler(CommandHandler('deposit', deposit))
dispatcher.add_handler(CommandHandler('myaddress', myaddress))
dispatcher.add_handler(CommandHandler('withdraw', withdraw))
dispatcher.add_handler(CommandHandler('balance', balance))
dispatcher.add_handler(CommandHandler('tip', tip))
dispatcher.add_handler(CommandHandler('rain', rain))
dispatcher.add_handler(CommandHandler('draw', draw))

# Start the bot
updater.start_polling()