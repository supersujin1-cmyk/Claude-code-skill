-- 가계부 기본 스키마. 모든 테이블은 로그인한 본인 데이터만 보이도록 RLS를 켭니다.
-- 실행: Supabase 대시보드 > SQL Editor에 붙여 넣고 Run.

create table accounts (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null default auth.uid() references auth.users on delete cascade,
  name         text not null,                 -- 예: "KB국민카드", "국민은행 입출금"
  kind         text not null check (kind in ('card', 'bank', 'brokerage')),
  institution  text not null,                 -- kb_card | samsung_card | kb_bank | kb_securities
  payment_type text check (payment_type in ('credit', 'debit')), -- 카드만: 연말정산 공제율 구분
  created_at   timestamptz not null default now()
);

create table transactions (
  id          text primary key,              -- 내용 기반 해시: 같은 파일 재업로드 시 중복 방지
  user_id     uuid not null default auth.uid() references auth.users on delete cascade,
  account_id  uuid not null references accounts on delete cascade,
  occurred_on date not null,
  amount      numeric(18, 2) not null,       -- 원화. 출금 음수, 입금 양수
  description text not null,
  category    text not null default '미분류',
  kind        text not null default 'normal'
              check (kind in ('normal', 'card_payment', 'transfer')),
  created_at  timestamptz not null default now()
);
create index on transactions (user_id, occurred_on);

create table balances (
  account_id  uuid not null references accounts on delete cascade,
  user_id     uuid not null default auth.uid() references auth.users on delete cascade,
  as_of       date not null,
  balance     numeric(18, 2) not null,       -- 원화
  primary key (account_id, as_of)
);

create table trades (
  id          text primary key,
  user_id     uuid not null default auth.uid() references auth.users on delete cascade,
  account_id  uuid not null references accounts on delete cascade,
  traded_on   date not null,
  symbol      text not null,
  name        text not null,
  market      text not null check (market in ('KR', 'US', 'OTHER')),
  side        text not null check (side in ('buy', 'sell')),
  quantity    numeric(20, 6) not null,
  price       numeric(20, 6) not null,       -- 거래 통화 기준
  currency    text not null default 'KRW',
  fx_rate     numeric(12, 4) not null default 1, -- 거래 시점 원화 환율
  fee         numeric(18, 2) not null default 0, -- 거래 통화 기준 수수료+세금
  created_at  timestamptz not null default now()
);

create table category_rules (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users on delete cascade,
  pattern     text not null,
  category    text not null,
  priority    int  not null default 100
);

alter table accounts       enable row level security;
alter table transactions   enable row level security;
alter table balances       enable row level security;
alter table trades         enable row level security;
alter table category_rules enable row level security;

create policy own_accounts       on accounts       for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_transactions   on transactions   for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_balances       on balances       for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_trades         on trades         for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy own_category_rules on category_rules for all using (user_id = auth.uid()) with check (user_id = auth.uid());
