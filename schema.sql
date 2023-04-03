CREATE TABLE users (
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    PRIMARY KEY (user_id)
);

CREATE TABLE balances (
    user_id INT NOT NULL,
    address VARCHAR(42) NOT NULL,
    balance DECIMAL(18, 9) NOT NULL,
    PRIMARY KEY (user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE addresses (
    user_id INT NOT NULL,
    address VARCHAR(42) NOT NULL,
    private_key VARCHAR(128) NOT NULL,
    PRIMARY KEY (user_id)
);

CREATE TABLE transfers (
    id INT NOT NULL AUTO_INCREMENT,
    sender_id INT NOT NULL,
    sender_username VARCHAR(255) NOT NULL,
    recipient_id INT NOT NULL,
    recipient_username VARCHAR(255) NOT NULL,
    amount DECIMAL(18, 9) NOT NULL,
    fees INT NOT NULL,
    tx_hash VARCHAR(66) NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE withdrawals (
    user_id INT NOT NULL,
    address VARCHAR(42) NOT NULL,
    amount DECIMAL(18, 9) NOT NULL,
    tx_hash VARCHAR(66) NOT NULL,
    PRIMARY KEY (user_id)
);

CREATE TABLE draw_entries (
    user_id INT NOT NULL,
    round INT NOT NULL,
    amount DECIMAL(18, 9) NOT NULL,
    PRIMARY KEY (user_id, round)
);