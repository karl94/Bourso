-- =====================================================================
-- BRVM Mon Portefeuille — schéma de la base Supabase (PostgreSQL)
-- À exécuter une seule fois : Supabase > SQL Editor > New query > coller > Run
-- =====================================================================

-- ---------- Référentiel des titres ----------
create table if not exists titres (
  code        text primary key,              -- symbole BRVM : SOGC, PALC, SNTS...
  nom         text not null,
  secteur     text,
  pays        text,
  actif       boolean not null default true,
  cree_le     timestamptz not null default now()
);

-- ---------- Cours quotidiens (alimentés par la collecte) ----------
create table if not exists cours_journaliers (
  code_titre     text not null references titres(code),
  date           date not null,
  cours_veille   numeric,
  ouverture      numeric,
  cloture        numeric not null,
  variation_pct  numeric,
  volume         bigint,
  statut         text not null default 'ok' check (statut in ('ok','a_verifier')),
  source         text not null,               -- brvm.org | boc
  collecte_le    timestamptz not null default now(),
  primary key (code_titre, date)
);
create index if not exists idx_cours_date on cours_journaliers(date desc);

-- ---------- Mes transactions ----------
create table if not exists transactions (
  id          bigint generated always as identity primary key,
  code_titre  text not null references titres(code),
  date        date not null,
  sens        text not null check (sens in ('achat','vente')),
  quantite    integer not null check (quantite > 0),
  cours       numeric not null check (cours > 0),
  frais       numeric not null default 0,
  poche       text not null check (poche in ('dividendes','swing')),
  note        text,
  cree_le     timestamptz not null default now()
);

-- ---------- Dividendes ----------
create table if not exists dividendes (
  id                bigint generated always as identity primary key,
  code_titre        text not null references titres(code),
  exercice          integer not null,
  montant_brut      numeric,
  montant_net       numeric,
  date_detachement  date,
  date_paiement     date,
  statut            text not null default 'annonce' check (statut in ('estime','annonce','paye')),
  source            text,
  unique (code_titre, exercice, date_detachement)
);

-- ---------- Mes objectifs par titre ----------
create table if not exists objectifs (
  code_titre          text primary key references titres(code),
  poche               text check (poche in ('dividendes','swing')),
  cible_achat         numeric,
  cible_vente         numeric,
  stop                numeric,
  conviction          text,
  source              text,                 -- ex. Bridge Conviction
  date_limite_sortie  date,
  suivi               boolean not null default true   -- dans la watchlist
);

-- ---------- Signaux calculés chaque soir ----------
create table if not exists signaux (
  code_titre       text not null references titres(code),
  date             date not null,
  score            integer not null check (score between 0 and 100),
  note_valo        numeric,
  note_dividende   numeric,
  note_momentum    numeric,
  note_liquidite   numeric,
  signal           text not null,
  explication      text,
  primary key (code_titre, date)
);

-- ---------- Veille ----------
create table if not exists veille (
  id                     bigint generated always as identity primary key,
  date                   date not null,
  source                 text not null,
  url                    text unique,
  titre                  text not null,
  categorie              text check (categorie in ('dividendes','resultats','ag','suspensions','actualite')),
  codes_titres           text[] default '{}',
  resume_ia              text,
  concerne_portefeuille  boolean not null default false,
  cree_le                timestamptz not null default now()
);

-- ---------- Alertes envoyées ----------
create table if not exists alertes (
  id          bigint generated always as identity primary key,
  date        timestamptz not null default now(),
  type        text not null,
  code_titre  text references titres(code),
  message     text not null,
  envoyee     boolean not null default false,
  lue         boolean not null default false
);

-- ---------- Journal technique des collectes ----------
create table if not exists collectes (
  id          bigint generated always as identity primary key,
  date_heure  timestamptz not null default now(),
  source      text not null,
  date_seance date,
  nb_titres   integer,
  nb_erreurs  integer,
  duree_s     numeric,
  statut      text not null,               -- ok | partiel | echec | pas_de_seance
  message     text
);

-- ---------- Réglages ----------
create table if not exists parametres (
  cle    text primary key,
  valeur jsonb not null
);
insert into parametres (cle, valeur) values
  ('poids_dividendes', '{"valo":35,"dividende":25,"momentum":25,"liquidite":15}'),
  ('poids_swing',      '{"valo":35,"dividende":25,"momentum":25,"liquidite":15}'),
  ('seuils',           '{"variation_inhabituelle_pct":5,"volume_inhabituel_x":3,"prise_benefices_pct":30,"rappel_detachement_jours":7}'),
  ('limite_variation_brvm_pct', '7.5')
on conflict (cle) do nothing;

-- ---------- Vue : dernier cours par titre ----------
create or replace view dernier_cours with (security_invoker = true) as
select distinct on (code_titre) code_titre, date, cloture, variation_pct, volume, statut
from cours_journaliers
order by code_titre, date desc;

-- ---------- Vue : positions recalculées depuis les transactions ----------
-- Prix de revient unitaire moyen pondéré, frais d'achat inclus.
create or replace view positions with (security_invoker = true) as
with mouvements as (
  select code_titre, poche,
         sum(case when sens='achat' then quantite else -quantite end) as quantite,
         sum(case when sens='achat' then quantite*cours + frais else 0 end) as cout_achats,
         sum(case when sens='achat' then quantite else 0 end) as qte_achetee
  from transactions
  group by code_titre, poche
)
select m.code_titre, t.nom, m.poche, m.quantite,
       round(m.cout_achats / nullif(m.qte_achetee,0)) as pru,
       d.cloture as cours, d.date as date_cours,
       m.quantite * d.cloture as valeur,
       round(m.quantite * (d.cloture - m.cout_achats / nullif(m.qte_achetee,0))) as plus_value,
       round(100 * (d.cloture / nullif(m.cout_achats / nullif(m.qte_achetee,0),0) - 1), 1) as plus_value_pct
from mouvements m
join titres t on t.code = m.code_titre
left join dernier_cours d on d.code_titre = m.code_titre
where m.quantite > 0;

-- ---------- Sécurité : accès réservé à l'utilisateur connecté ----------
-- La collecte utilise la clé « service_role », qui contourne ces règles.
-- IMPORTANT : désactiver les inscriptions (Authentication > Sign In / Providers > Allow new users to sign up = off)
-- pour que vous soyez le seul utilisateur « authenticated ».
do $$
declare t text;
begin
  foreach t in array array['titres','cours_journaliers','transactions','dividendes','objectifs','signaux','veille','alertes','collectes','parametres']
  loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists acces_proprietaire on %I', t);
    execute format('create policy acces_proprietaire on %I for all to authenticated using (true) with check (true)', t);
  end loop;
end $$;
