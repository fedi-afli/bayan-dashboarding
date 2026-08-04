CREATE TABLE IF NOT EXISTS sales (
    discount FLOAT NULL,
    customer_name VARCHAR(255) NULL,
    unit_price FLOAT NULL,
    sale_date DATE NULL,
    invoice_number VARCHAR(255) NULL,
    order_date DATE NULL,
    product_name VARCHAR(255) NOT NULL,
    order_line_number INTEGER NULL,
    quantity INTEGER NOT NULL
);