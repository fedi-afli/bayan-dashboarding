CREATE TABLE IF NOT EXISTS sales (
    sale_date DATE NULL,
    discount FLOAT NULL,
    quantity INTEGER NOT NULL,
    customer_name VARCHAR(255) NULL,
    unit_price FLOAT NULL,
    invoice_number VARCHAR(255) NULL,
    product_name VARCHAR(255) NOT NULL,
    order_line_number INTEGER NULL
);