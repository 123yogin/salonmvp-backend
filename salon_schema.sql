
-- Salon Management MVP SQL Schema (PostgreSQL)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  phone VARCHAR(20) UNIQUE,
  email VARCHAR(255) UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Salons
CREATE TABLE salons (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  owner_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(255) NOT NULL,
  address TEXT,
  timezone VARCHAR(64) DEFAULT 'Asia/Kolkata',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Staff
CREATE TABLE staff (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  salon_id UUID NOT NULL REFERENCES salons(id),
  name VARCHAR(255) NOT NULL,
  phone VARCHAR(20),
  role VARCHAR(50),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Services
CREATE TABLE services (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  salon_id UUID NOT NULL REFERENCES salons(id),
  name VARCHAR(255) NOT NULL,
  default_price NUMERIC(10,2) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_services_salon ON services(salon_id, is_active);

-- Payment method enum
DO $$ BEGIN
    CREATE TYPE payment_method AS ENUM ('cash','upi');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Service Logs
CREATE TABLE service_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  salon_id UUID NOT NULL REFERENCES salons(id),
  staff_id UUID REFERENCES staff(id),
  service_id UUID REFERENCES services(id),
  custom_service VARCHAR(255),
  price NUMERIC(10,2) NOT NULL,
  payment_method payment_method NOT NULL,
  served_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_logs_salon_date ON service_logs(salon_id, served_at);
CREATE INDEX idx_logs_salon_payment ON service_logs(salon_id, payment_method);

-- Daily Closing Summary
CREATE TABLE daily_closings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  salon_id UUID NOT NULL REFERENCES salons(id),
  date DATE NOT NULL,
  closed_at TIMESTAMPTZ NOT NULL,
  total_revenue NUMERIC(10,2) NOT NULL,
  cash_total NUMERIC(10,2) NOT NULL,
  upi_total NUMERIC(10,2) NOT NULL,
  UNIQUE (salon_id, date)
);
