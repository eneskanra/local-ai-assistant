
-- 1. Customers
CREATE TABLE customers (
    customer_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL
);

-- 2. Products
CREATE TABLE products (
    product_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    price NUMERIC(12,2) NOT NULL CHECK (price >= 0)
);

-- 3. Orders
CREATE TABLE orders (
    order_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date DATE NOT NULL
);

-- 4. Order Items
CREATE TABLE order_items (
    order_item_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0)
);

-- Örnek müşteriler
INSERT INTO customers (name, city) VALUES
('Ahmet Yılmaz', 'İstanbul'),
('Ayşe Demir', 'Ankara'),
('Mehmet Kaya', 'İzmir'),
('Zeynep Çelik', 'İstanbul'),
('Can Arslan', 'Bursa');

-- Örnek ürünler
INSERT INTO products (product_name, price) VALUES
('Laptop', 45000),
('Monitor', 9000),
('Keyboard', 2500),
('Mouse', 1200),
('Headset', 3500);

-- Örnek siparişler
INSERT INTO orders (customer_id, order_date) VALUES
(1, '2026-09-10'),
(2, '2026-09-15'),
(1, '2026-10-02'),
(3, '2026-10-12'),
(4, '2026-10-20'),
(5, '2026-10-25'),
(2, '2026-11-01');

-- Sipariş kalemleri
INSERT INTO order_items
(order_id, product_id, quantity, unit_price)
VALUES
(1, 1, 1, 45000),
(1, 3, 2, 2500),
(2, 2, 2, 9000),
(3, 4, 3, 1200),
(3, 5, 1, 3500),
(4, 1, 1, 45000),
(5, 2, 1, 9000),
(5, 3, 1, 2500),
(6, 5, 2, 3500),
(7, 1, 1, 45000);

-- Salt okunur ai_reader kullanıcısı db/02_create_reader.sh
-- içinde, şifre ortam değişkeninden okunarak oluşturulur.
