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
from web3.auto import w3

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
/register - Create a BSC address
/deposit - Get your deposit address for NYANTE.
/withdraw <address> <amount> NYANTE - withdraw tokens to an external address.
/balance - Get your token balance.
/tip <amount> <NYANTE> <username> - Send tokens to another user.
/rain <amount> - Send tokens to all active users in the chat.
/draw <amount> <num_winners> <hashtag> - Start a giveaway and randomly reward users who reply with the specified hashtag.
/help - Show this help message.'''
    update.message.reply_text(help_text)

def register(update: Update, context: CallbackContext):
    """Register the user and generate a BSC address."""
    user_id = update.message.from_user.id
    if update.message.chat.type != 'private':
        update.message.reply_text('This command can only be used in a private chat.')
        return
    # Check if user is already registered
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    if result is not None:
        update.message.reply_text('You are already registered.')
        return
    # Generate new BSC address and private key
    account = w3.eth.account.create()
    address = account.address
    private_key = account.privateKey.hex()
    # Check if address is valid
    if not Web3.isAddress(address):
        update.message.reply_text('Error: Invalid BSC address generated. Please try again.')
        return
    # Insert new address and private key into database
    cursor.execute('INSERT INTO addresses (user_id, address, private_key) VALUES (%s, %s, %s)', (user_id, address, private_key))
    db.commit()
    # Insert new user into database
    username = update.message.from_user.username
    cursor.execute('INSERT INTO users (user_id, username) VALUES (%s, %s)', (user_id, username))
    db.commit()
    # Send confirmation message
    message = f'You have been registered with the following BSC address:\n\n{address}\n\nPlease use this address to deposit BNB or BEP20 tokens to your account.'
    context.bot.send_message(chat_id=user_id, text=message)


import requests

def get_bnb_balance(address):
    url = f'https://api.bscscan.com/api?module=account&action=balance&address={address}&tag=latest&apikey=YourApiKeyToken'
    response = requests.get(url)
    if response.status_code == 200:
        balance = int(response.json()['result']) / 10**18
        return balance
    else:
        return None


def register_all(update: Update, context: CallbackContext):
    """Register all users in the chat and generate a BSC address."""
    chat_id = update.message.chat_id
    if update.message.chat.type != 'supergroup':
        update.message.reply_text('This command can only be used in a supergroup.')
        return
    # Get number of members in the chat
    num_members = context.bot.get_chat_members_count(chat_id)
    # Loop through each member in the chat
    for i in range(num_members):
        member = context.bot.get_chat_member(chat_id, i)
        user_id = member.user.id
        # Check if user is already registered
        cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        if result is not None:
            continue
        # Generate new BSC address and private key
        account = w3.eth.account.create()
        address = account.address
        private_key = account.privateKey.hex()
        # Check if address is valid
        if not Web3.isAddress(address):
            continue
        # Insert new address and private key into database
        cursor.execute('INSERT INTO addresses (user_id, address, private_key) VALUES (%s, %s, %s)', (user_id, address, private_key))
        db.commit()
        # Insert new user into database
        username = member.user.username
        cursor.execute('INSERT INTO users (user_id, username) VALUES (%s, %s)', (user_id, username))
        db.commit()
    # Send confirmation message
    message = 'All users in the chat have been registered with a BSC address.'
    context.bot.send_message(chat_id=chat_id, text=message)

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
        # Get balance of user's address
        balance = nyante_contract.functions.balanceOf(address).call()
        # Get balance of BNB
        bnb_balance = get_bnb_balance(address)
        if bnb_balance is None:
            bnb_balance = 0
        # Save deposit address and balances to balances table
        cursor.execute('INSERT INTO balances (user_id, address, balance, bnb_balance) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE address = %s, balance = %s, bnb_balance = %s', (user_id, address, balance, bnb_balance, address, balance, bnb_balance))
        db.commit()
        message = f'Your deposit address is: {address}\n\nPlease use this address to deposit Nyantereum International for transfer.\n\nThe current balance of tokens is: \nAmount: {balance // 10**18} [NYANTE]\nNyantereum International\n\nBinance [BNB]: Amount {bnb_balance:.8f}'
        context.bot.send_message(chat_id=user_id, text=message)
        # Send private key in a direct message
        context.bot.send_message(chat_id=user_id, text=f'Your private key is:\n{private_key}\n\nPlease keep your private key safe and do not share it with anyone.')
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
    """Get the NYANTE balance of the user."""
    user_id = update.message.from_user.id
    if update.message.chat.type == 'private':
        # Get user's address and balance from database
        cursor.execute('SELECT address, balance FROM balances WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        if result is None:
            update.message.reply_text('Error: No deposit address found. Please use the /deposit command to generate a deposit address.')
            return
        address = result[0]
        balance = result[1]

        # Get balance of NYANTE contract
        nyante_balance = nyante_contract.functions.balanceOf(address).call()

        # Get total withdrawals and fees from transfers table
        cursor.execute('SELECT SUM(amount) FROM transfers WHERE sender_id = %s', (user_id,))
        result = cursor.fetchone()
        total_withdrawals = Decimal(result[0] or 0)

        cursor.execute('SELECT SUM(fees) FROM transfers WHERE sender_id = %s', (user_id,))
        result = cursor.fetchone()
        total_fees = Decimal(result[0] or 0)

        # Calculate withdrawable balance
        withdrawable_balance = balance - total_withdrawals - total_fees

        # Get BNB balance from balances table
        cursor.execute('SELECT bnb_balance FROM balances WHERE user_id = %s AND address = %s', (user_id, address))
        result = cursor.fetchone()
        bnb_balance = Decimal(result[0] or 0)

        # Calculate fees
        fees = Decimal('0')
        if balance >= Decimal('1000000'):
            fees = balance * Decimal('0.01')
            fees = fees.quantize(Decimal('0.00001'))

        # Send message to user
        message = f'Your balance is: {round(float(balance / 10 ** 18), 3)} NYANTE\n\nThe current balance of NYANTE tokens on your deposit address ({address}) is: {int(nyante_balance / 10 ** 18)} NYANTE\n\nYou have withdrawn a total of {int(total_withdrawals)} NYANTE with {int(total_fees)} NYANTE in fees.\n\nYour withdrawable balance is: {round(float(withdrawable_balance / 10 ** 18), 3)} NYANTE\n\nYour BNB balance is: {bnb_balance:.8f}\n\nPlease note that balances above 1,000,000 NYANTE are withdrawable.'
        context.bot.send_message(chat_id=user_id, text=message)
    else:
        update.message.reply_text('This command can only be used in a private chat.')
        

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

NYANTE_TOKEN_ADDRESS = config.get('NYANTE', 'contract_address')

def withdraw(update: Update, context: CallbackContext):
    """Withdraw tokens to an external address."""
    user_id = update.message.from_user.id
    args = context.args
    if len(args) != 2:
        update.message.reply_text('Usage: /withdraw <address> <amount>')
        return
    address = args[0]
    if not address.startswith('0x'):
        address = '0x' + address
    if not web3.isAddress(address):
        update.message.reply_text('Invalid address.')
        return
    address = Web3.toChecksumAddress(address)
    amount = Decimal(args[1]) * Decimal(10 ** 18)
    if amount < 1000000 * Decimal(10 ** 18):
        update.message.reply_text('Minimum withdrawal amount is 1000000 tokens.')
        return

    # Get all addresses and balances from balances table
    cursor.execute('SELECT address, balance FROM balances WHERE balance >= %s', (amount,))
    results = cursor.fetchall()
    if len(results) == 0:
        update.message.reply_text('Insufficient balance.')
        return

    # Calculate total balance and fees
    total_balance = sum([Decimal(result[1]) for result in results])
    fees = Decimal('0')
    if total_balance >= Decimal('1000000'):
        fees = total_balance * Decimal('0.01')
        fees = fees.quantize(Decimal('0.00001'))

    # Get transfer fee fund address from config file
    transfer_fee_fund_address = config['transfer_fee_fund_address']

    # Get balance of transfer fee fund address
    transfer_fee_fund_balance = nyante_contract.functions.balanceOf(transfer_fee_fund_address).call()

    # Check if transfer fee fund has enough balance to cover fees
    if fees > transfer_fee_fund_balance:
        update.message.reply_text('Error: Insufficient transfer fee fund balance. Please try again later.')
        return

    # Create list of transfer objects
    transfers = []
    for result in results:
        transfer = {
            'address': result[0],
            'amount': result[1],
        }
        transfers.append(transfer)

    # Create unsigned transaction
    nonce = web3.eth.getTransactionCount(transfer_fee_fund_address)
    tx_data = nyante_contract.encodeABI(fn_name='multiTransfer', args=[transfers])
    tx = {
        'nonce': nonce,
        'gasPrice': web3.eth.gas_price,
        'gas': 2000000,
        'to': NYANTE_TOKEN_ADDRESS,
        'value': 0,
        'data': tx_data,
    }

    # Sign transaction with transfer fee fund address private key
    transfer_fee_fund_address_private_key = config['transfer_fee_fund_address_private_key']
    account = Account.from_key(transfer_fee_fund_address_private_key)
    signed_tx = account.sign_transaction(tx)

    # Send signed transaction
    tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)

    # Update balances in database
    for result in results:
        cursor.execute('UPDATE balances SET balance = balance - %s WHERE user_id = %s AND address = %s', (result[1], user_id, result[0]))
    db.commit()

    # Update transfer fee fund balance in database
    cursor.execute('UPDATE balances SET balance = balance + %s WHERE address = %s', (fees, transfer_fee_fund_address))
    db.commit()

    # Save transfer to database
    cursor.execute('INSERT INTO transfers (sender_id, sender_username, recipient_id, recipient_username, amount, fees, tx_hash) VALUES (%s, %s, %s, %s, %s, %s, %s)', (user_id, update.message.from_user.username, EXTERNAL_WITHDRAW_ADDRESS_ID, 'External Withdraw Address', total_balance, fees, tx_hash.hex()))
    db.commit()

    # Send confirmation message to user
    message = f'{total_balance // 10 ** 18} NYANTE has been withdrawn to address {address} with a fee of {fees // 10 ** 18} NYANTE.\n\nTransaction hash: {tx_hash.hex()}'
    context.bot.send_message(chat_id=user_id, text=message)


def transfer(update: Update, context: CallbackContext):
    """Transfer NYANTE tokens from one user to another."""
    # Get sender and recipient user IDs and amount from message
    sender_id = update.message.from_user.id
    if context.args[0] == '/tip':
        recipient_username = context.args[2]
        amount = Decimal(context.args[1]) * Decimal(10 ** 18)
    elif context.args[0] == '/transfer':
        recipient_username = context.args[2]
        amount = Decimal(context.args[1]) * Decimal(10 ** 18)
    else:
        update.message.reply_text('Usage: /tip <amount> NYANTE @username or /transfer <amount> NYANTE @username')
        return
    # Check if sender has enough NYANTE tokens
    sender_address = get_address(sender_id)
    sender_balance = nyante_contract.functions.balanceOf(sender_address).call()
    if sender_balance < amount:
        update.message.reply_text('Error: Insufficient balance.')
        return
    # Get recipient user ID
    cursor.execute('SELECT user_id FROM users WHERE username = %s', (recipient_username,))
    result = cursor.fetchone()
    if result is None:
        update.message.reply_text(f'User {recipient_username} not found.')
        return
    recipient_id = result[0]
    # Check if recipient is the withdraw address
    if recipient_id == WITHDRAW_ADDRESS_ID:
        # Send NYANTE tokens to withdraw address
        tx_hash = nyante_contract.functions.transfer(WITHDRAW_ADDRESS, amount).transact({'from': sender_address})
        # Wait for transaction to be mined
        receipt = web3.eth.waitForTransactionReceipt(tx_hash)
        # Update balances in database
        cursor.execute('UPDATE balances SET balance = balance - %s WHERE user_id = %s', (amount, sender_id))
        # Calculate fees
        fees = int(amount * Decimal(0.01))
        # Deduct fees from deposit address
        cursor.execute('UPDATE balances SET balance = balance - %s WHERE user_id = %s', (fees, DEPOSIT_ADDRESS_ID))
        # Save transfer to database
        cursor.execute('INSERT INTO transfers (sender_id, sender_username, recipient_id, recipient_username, amount, fees, tx_hash) VALUES (%s, %s, %s, %s, %s, %s, %s)', (sender_id, update.message.from_user.username, WITHDRAW_ADDRESS_ID, 'Withdraw Address', amount, fees, tx_hash.hex()))
        db.commit()
        update.message.reply_text(f'Transaction sent: https://bscscan.com/tx/{tx_hash.hex()}')
        # Send message to sender
        sender_message = f'You withdrew {amount / Decimal(10 ** 18)} NYANTE to the withdraw address. Transaction hash: {receipt.transactionHash.hex()}'
        context.bot.send_message(chat_id=sender_id, text=sender_message)
    else:
        # Save transfer to database
        cursor.execute('INSERT INTO transfers (sender_id, sender_username, recipient_id, recipient_username, amount, fees) VALUES (%s, %s, %s, %s, %s, %s)', (sender_id, update.message.from_user.username, recipient_id, recipient_username, amount, 0))
        db.commit()
        # Update balances in database
        cursor.execute('UPDATE balances SET balance = balance + %s WHERE user_id = %s', (amount, recipient_id))
        cursor.execute('UPDATE balances SET balance = balance - %s WHERE user_id = %s', (amount, sender_id))
        # Send message to sender
        sender_message = f'You transferred {amount / Decimal(10 ** 18)} NYANTE to {recipient_username}.'
        context.bot.send_message(chat_id=sender_id, text=sender_message)
        # Send message to recipient
        recipient_message = f'You received {amount / Decimal(10 ** 18)} NYANTE from {update.message.from_user.username}.'
        context.bot.send_message(chat_id=recipient_id, text=recipient_message)
        # Check if recipient balance is above 1000000 and send message to recipient
        cursor.execute('SELECT balance FROM balances WHERE user_id = %s', (recipient_id,))
        result = cursor.fetchone()
        if result[0] >= Decimal(1000000) * Decimal(10 ** 18):
            recipient_message = f'Your balance is now above 1,000,000 NYANTE and is withdrawable.'
            context.bot.send_message(chat_id=recipient_id, text=recipient_message)


def rain(update: Update, context: CallbackContext):
    """Distribute tokens to a group of users."""
    user_id = update.message.from_user.id
    args = context.args
    if len(args) != 2:
        update.message.reply_text('Usage: /rain <group> <amount>')
        return
    group = args[0]
    amount = Decimal(args[1]) * Decimal(10 ** 18)
    if amount < Decimal(10 ** 18):
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
    update.message.reply_text(f'You rained {amount / Decimal(10 ** 18)} tokens on {num_users} users in group {group}.')

def draw(update: Update, context: CallbackContext):
    """Participate in a draw and have a chance to win tokens."""
    user_id = update.message.from_user.id
    args = context.args
    if len(args) != 3:
        update.message.reply_text('Usage: /draw <amount> <hashtag> <message>')
        return
    amount = Decimal(args[0]) * Decimal(10 ** 18)
    if amount < Decimal(10 ** 18):
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
        update.message.reply_text(f'{num_participants} participants entered the draw with {hashtag}. Each participant won {amount_per_participant / Decimal(10 ** 18)} tokens. Message: {message}')
    else:
        # Add entry to draw_entries table
        cursor.execute('INSERT INTO draw_entries (user_id, round, amount) VALUES (%s, %s, %s)', (user_id, current_round, amount))
        db.commit()
        update.message.reply_text(f'You have entered the draw with {amount / Decimal(10 ** 18)} tokens. Hashtag: {hashtag}. Message: {message}')

# Initialize the Telegram bot
updater = Updater(token=TELEGRAM_TOKEN, use_context=True)

# Get the dispatcher to register handlers
dispatcher = updater.dispatcher

def on_new_chat_members(update: Update, context: CallbackContext):
    """Automatically run the register_all command when a new member joins the chat."""
    register_all(update, context)

# Define message handlers
start_handler = CommandHandler('start', start)
help_handler = CommandHandler('help', help)
register_handler = CommandHandler('register', register)
register_all_handler = CommandHandler('register_all', register_all)
deposit_handler = CommandHandler('deposit', deposit)
withdraw_handler = CommandHandler('withdraw', withdraw)
balance_handler = CommandHandler('balance', balance)
tip_handler = CommandHandler('tip', tip)
transfer_handler = CommandHandler('transfer', transfer)
rain_handler = CommandHandler('rain', rain)
draw_handler = CommandHandler('draw', draw)
on_new_chat_members_handler = MessageHandler(Filters.status_update.new_chat_members, on_new_chat_members)

# Add message handlers to dispatcher
dispatcher.add_handler(start_handler)
dispatcher.add_handler(help_handler)
dispatcher.add_handler(register_handler)
dispatcher.add_handler(register_all_handler)
dispatcher.add_handler(deposit_handler)
dispatcher.add_handler(withdraw_handler)
dispatcher.add_handler(balance_handler)
dispatcher.add_handler(tip_handler)
dispatcher.add_handler(transfer_handler)
dispatcher.add_handler(rain_handler)
dispatcher.add_handler(draw_handler)
dispatcher.add_handler(on_new_chat_members_handler)

# Add command handlers
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('help', help))
dispatcher.add_handler(CommandHandler('register', register))
dispatcher.add_handler(CommandHandler('deposit', deposit))
dispatcher.add_handler(CommandHandler('myaddress', myaddress))
dispatcher.add_handler(CommandHandler('withdraw', withdraw))
dispatcher.add_handler(CommandHandler('balance', balance))
dispatcher.add_handler(CommandHandler('transfer', transfer))
dispatcher.add_handler(CommandHandler('rain', rain))
dispatcher.add_handler(CommandHandler('draw', draw))

# Start the bot
updater.start_polling()