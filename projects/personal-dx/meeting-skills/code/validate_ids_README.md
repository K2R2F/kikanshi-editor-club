# validate_ids.py 使用方法

議事録作成Skillsで使用する **S-ID（Scene）** と **M-ID（Meaning Unit）** の採番・整合性点検用補助スクリプトです。

## 1. 安全な自動採番

Markdown内で、採番したい箇所を次のように書きます。

```markdown
## S-AUTO
```

または

```markdown
### M-AUTO
```

`{{S-ID}}` / `{{M-ID}}` も利用できます。

実行例：

```bash
python validate_ids.py number 02_シーン構造分析.md --type scene
python validate_ids.py number 03_議事内容整理.md --type meaning
```

書換え前のファイルは自動的に `.bak` として保存されます。

### 既存IDの再採番

```bash
python validate_ids.py number 02_シーン構造分析.md --type scene --renumber
```

既存参照を壊す可能性があるため、通常運用では推奨しません。

---

## 2. 整合性点検

```bash
python validate_ids.py check \
  --scene 02_シーン構造分析.md \
  --meaning 03_議事内容整理.md \
  --minutes 04_議事録.md
```

点検項目：

- S-ID / M-ID の重複
- 文書内のID順序
- 欠番
- 未採番 `S-AUTO` / `M-AUTO`
- M-IDから存在しないS-IDへの参照
- 議事録の `source` コメントから存在しないIDへの参照

議事録の根拠コメント例：

```html
<!-- source: M-023, M-024 / S-007 -->
```

## 3. 終了コード

- `0`：エラーなし（警告だけの場合も0）
- `1`：整合性エラーあり
- `2`：入力・実行エラー

CIやSkillからの自動点検にも利用できます。
