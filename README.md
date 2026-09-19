# 每日待辦清單

自己在用的待辦 App。首頁是月曆,點某一天進去就能記那天要做的事,做完打勾會劃掉。

用 Streamlit 寫的,資料放 Supabase,所以關掉再開資料還在,手機瀏覽器也能用。

## 用起來像這樣

月曆上每天會標顏色:綠色是當天的事都做完了,橘色是還有沒做完的,藍色菱形是今天。

點進某一天可以新增任務、選分類(工作/生活/學習/其他)、打勾、按鉛筆改字或刪掉,上面有進度條顯示做完幾項。

登入是 Email + 密碼,每個人只看得到自己的清單。有勾「記住我」的話 30 天內重新整理不會被登出。

## 自己跑起來

1. 到 [supabase.com](https://supabase.com) 開一個專案,在 SQL Editor 把 `supabase_schema.sql` 貼上執行
2. 把 `.streamlit/secrets.toml.example` 複製成 `.streamlit/secrets.toml`,填入 Supabase 的 Project URL 和 publishable key
3. 然後:

```bash
pip install -r requirements.txt
streamlit run app.py
```

金鑰要用 publishable(或舊的 anon),不要用 secret / service_role,那兩把會繞過 RLS,等於整個資料庫對外開放。

## 部署

推上 GitHub 之後到 [streamlit.io/cloud](https://streamlit.io/cloud) 開一個 App,在 Settings → Secrets 貼上跟 `secrets.toml` 一樣的內容就好。

## 還想加的

- 提醒通知
- 每天/每週固定要做的事可以自動帶出來
