CREATE TABLE IF NOT EXISTS sales (
    product_name VARCHAR(255) NOT NULL,
    order_line_number INTEGER NULL,
    discount FLOAT NULL,
    unit_price FLOAT NULL,
    invoice_number VARCHAR(255) NULL,
    quantity INTEGER NOT NULL,
    sale_date DATE NULL,
    customer_name VARCHAR(255) NULL
);