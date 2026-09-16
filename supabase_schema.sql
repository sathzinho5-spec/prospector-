-- ============================================================
-- PROSPECTOR - Schema completo do Supabase (arquivo único)
-- Cole TUDO no SQL Editor do seu projeto e clique Run.
-- É idempotente: pode rodar quantas vezes quiser.
-- ============================================================

-- ---------- LEADS (Maps + funil) ----------
create table if not exists leads (
  id text primary key,
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
  score_oportunidade integer,
  nivel text,
  oportunidades text,
  pitch_whatsapp text,
  contato_status text default 'novo',
  observacao text,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- ---------- FILA DE DISPARO ----------
create table if not exists fila_disparo (
  id bigint generated always as identity primary key,
  lead_id text references leads(id),
  nome text,
  telefone text not null,
  mensagem text not null,
  status text default 'pendente',
  tentativas integer default 0,
  agendado_para timestamp with time zone default now(),
  enviado_em timestamp with time zone,
  erro text,
  origem text,
  created_at timestamp with time zone default now()
);

-- ---------- GIGANTES INVISÍVEIS (CNPJ) ----------
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
  telefone text,
  telefone2 text,
  email text,
  created_at timestamp with time zone default now()
);

create table if not exists vistos_cnpj (
  cnpj text primary key,
  visto_em timestamp with time zone default now()
);

-- ---------- ÍNDICES ----------
create index if not exists idx_leads_uf on leads(estado);
create index if not exists idx_leads_cidade on leads(cidade);
create index if not exists idx_leads_categoria on leads(categoria);
create index if not exists idx_leads_score on leads(score_oportunidade desc);
create index if not exists idx_leads_status on leads(contato_status);
create index if not exists idx_fila_status on fila_disparo(status);
create index if not exists idx_empresas_uf on empresas_grandes(uf);
create index if not exists idx_empresas_capital on empresas_grandes(capital);
create index if not exists idx_empresas_cidade on empresas_grandes(cidade);
create index if not exists idx_empresas_email on empresas_grandes(email) where email is not null;

-- ---------- RLS (service_role) ----------
alter table leads disable row level security;
alter table fila_disparo disable row level security;
alter table empresas_grandes disable row level security;
alter table vistos_cnpj disable row level security;
