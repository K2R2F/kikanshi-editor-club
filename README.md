# 機関紙編集者クラブ 公開資料

機関紙編集者クラブに関する公開ページと、記事ごとの参考資料を管理するリポジトリです。

## 公開ページ

- 総合入口: `docs/index.html`
- 「個人的DXのススメ」一覧: `docs/personal-dx/index.html`
- 「コンテキストから議事録スキルを作る」: `docs/personal-dx/meeting-skills/index.html`

GitHub Pagesでは、`main`ブランチの `/docs` を公開元に設定してください。

## リポジトリ構成

```text
docs/                               GitHub Pages
projects/personal-dx/meeting-skills 公開確認済みの資料
release/                            Release登録用のZIP
```

## 更新手順

1. `projects/personal-dx/meeting-skills/` の公開資料を更新する
2. `PUBLICATION_CHECKLIST.md` に沿って公開前確認を再実施する
3. ページの版番号・更新日・変更履歴を更新する
4. `downloads/` の内容からZIPを作り直す
5. 新しいGitHub Releaseを公開する
6. ページのダウンロードリンクと変更履歴を更新する
7. 固定URLとQRコードが引き続き有効か確認する

## ライセンス

ライセンスは未決定です。公開・再利用条件は、筆者による確認後に明記します。
