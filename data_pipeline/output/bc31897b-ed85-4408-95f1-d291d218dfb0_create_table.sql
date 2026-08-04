CREATE TABLE IF NOT EXISTS sales (
    discount FLOAT NULL,
    invoice_number VARCHAR(255) NULL,
    unit_price FLOAT NULL,
    quantity INTEGER NOT NULL,
    order_line_number INTEGER NULL,
    customer_name VARCHAR(255) NULL,
    sale_date DATE NULL,
    order_date DATE NULL,
    product_name VARCHAR(255) NOT NULL
);