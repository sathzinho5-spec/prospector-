-- CRM: adiciona observacao nos leads (rode no SQL Editor se a tabela já existe)
-- https://supabase.com/dashboard/project/licvxiszgloeyqiaibbv/sql/new

alter table leads add column if not exists observacao text;
alter table leads add column if not exists updated_at_tz timestamp with time zone;
