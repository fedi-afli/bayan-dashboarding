CREATE TABLE IF NOT EXISTS sales (
    customer_name VARCHAR(255) NULL,
    sale_date DATE NULL,
    invoice_number VARCHAR(255) NULL,
    unit_price FLOAT NULL,
    order_line_number INTEGER NULL,
    product_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL,
    discount FLOAT NULL
);