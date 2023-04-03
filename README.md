# Currency Service ( -° NYANTEbot in Telegram)
* This is a BEP20 tip bot for Telegram. It allows users to send and receive tokens in a Telegram chat.

## Installation
* Clone the repository: git clone https://github.com/TRRXITTE/tipbot
* Install the required packages: pip install -r requirements.txt
* Create a .env file in the root directory and add the following variables:
```
PRIVATE_KEY=<your-private-key>
```
* Create a config.ini file in the root directory and add the following sections and options:
```
[Telegram]
token=<your-telegram-bot-token>

[BEP20]
contract_address=<your-bep20-contract-address>
deposit_address=<your-bep20-deposit-address>

[Database]
host = localhost
port = 3306
database = tipbotdb
user = tipbotuser
password = tipbotpassword
```

* Run the bot: **python main.py**

### Usage
* Currency Service supports the following commands:
```
/deposit - Get your deposit address.
/withdraw <address> <amount> - Withdraw tokens to an external address.
/balance - Get your token balance.
/tip <amount> <username> - Send tokens to another user.
/rain <amount> - Send tokens to all active users in the chat.
/draw <amount> <num_winners> <hashtag> - Start a giveaway and randomly reward users who reply with the specified hashtag.
/help - Show the help message.
```

##### About
* Currency Service | BEP20 with integrated fee fund

#### License
This project is licensed under the MIT License - see the LICENSE file for details.