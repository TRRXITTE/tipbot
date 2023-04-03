CREATE TABLE users (
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    `group` VARCHAR(255) NOT NULL,
    PRIMARY KEY (user_id)
);

CREATE TABLE balances (
    user_id INT NOT NULL,
    balance DECIMAL(18, 9) NOT NULL,
    PRIMARY KEY (user_id)
);

CREATE TABLE addresses (
    user_id INT NOT NULL,
    address VARCHAR(42) NOT NULL,
    private_key VARCHAR(128) NOT NULL,
    PRIMARY KEY (user_id)
);

CREATE TABLE draw_entries (
    user_id INT NOT NULL,
    round INT NOT NULL,
    amount DECIMAL(18, 9) NOT NULL,
    PRIMARY KEY (user_id, round)
);