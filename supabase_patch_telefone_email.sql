-- Adiciona telefone e e-mail na tabela de gigantes
-- Cole no SQL Editor: https://supabase.com/dashboard/project/pbedbvjxohbocfrtkpgn/sql/new

alter table empresas_grandes add column if not exists telefone text;
alter table empresas_grandes add column if not exists email text;
alter table empresas_grandes add column if not exists telefone2 text;

create index if not exists idx_empresas_email on empresas_grandes(email) where email is not null;
