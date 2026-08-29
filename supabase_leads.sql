-- Tabela para todos os leads do Maps (Prospector)
-- Cole no SQL Editor do Supabase: https://supabase.com/dashboard/project/pbedbvjxohbocfrtkpgn/sql/new

create table if not exists leads (
  id text primary key, -- hash de nome+endereco
  nome text not null,
  categoria text,
  nota text,
  avaliacoes text,
  endereco text,
  bairro text,
  cidade text,
  estado text,
  telefone text,
  website text,
  horarios text,
  status_funcionamento text,
  preco text,
  plus_code text,
  atributos text,
  latitude text,
  longitude text,
  foto text,
  descricao text,
  consulta text,
  url text,
  created_at timestamp with time zone default now()
);

create index if not exists idx_leads_uf on leads(estado);
create index if not exists idx_leads_cidade on leads(cidade);
create index if not exists idx_leads_categoria on leads(categoria);

alter table leads disable row level security;
