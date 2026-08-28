-- Copie e cole no SQL Editor do Supabase (https://supabase.com/dashboard/project/pbedbvjxohbocfrtkpgn/sql/new)
-- Cria tabelas para o Prospector - Gigantes Invisíveis

create table if not exists empresas_grandes (
  cnpj text primary key,
  razao text not null,
  fantasia text,
  capital numeric,
  porte text,
  uf text,
  cidade text,
  cnae text,
  situacao text,
  created_at timestamp with time zone default now()
);

create table if not exists vistos_cnpj (
  cnpj text primary key,
  visto_em timestamp with time zone default now()
);

-- Indices para busca rápida
create index if not exists idx_empresas_uf on empresas_grandes(uf);
create index if not exists idx_empresas_capital on empresas_grandes(capital);
create index if not exists idx_empresas_cidade on empresas_grandes(cidade);

-- Desativa RLS para uso com service_role (ou configure como preferir)
alter table empresas_grandes disable row level security;
alter table vistos_cnpj disable row level security;
