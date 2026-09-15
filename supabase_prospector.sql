-- Prospector: leads + fila de disparo na nuvem
-- Cole no SQL Editor do SEU projeto Supabase (novo) e clique Run

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
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

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

create index if not exists idx_leads_uf on leads(estado);
create index if not exists idx_leads_score on leads(score_oportunidade desc);
create index if not exists idx_leads_status on leads(contato_status);
create index if not exists idx_fila_status on fila_disparo(status);

alter table leads disable row level security;
alter table fila_disparo disable row level security;
