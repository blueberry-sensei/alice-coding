# ALICE.project.md — Đặc tả project ‹chưa init›

> **File này thuộc về project của bạn.** [`ALICE.md`](ALICE.md) (hiến pháp, thuộc template) sẽ bị `npm run update` ghi đè khi có bản mới; **file này thì không bao giờ**.
> Vì vậy mọi thứ đặc thù project đều nằm ở đây, không nhồi vào `ALICE.md`.
>
> [`INITIALIZATION.md`](INITIALIZATION.md) điền file này từ source thật. Chưa init thì các mục dưới còn nguyên `‹đặc tả khi init›`.

## 1. Tech stack & runtime
‹đặc tả khi init — ngôn ngữ, framework, phiên bản, hạ tầng chạy; verify từ file config thật›

## 2. Convention repo
‹đặc tả khi init — ngôn ngữ code/UI/commit, lint, format, pattern chủ đạo, quy ước đặt tên›

## 3. Module map
‹đặc tả khi init — bảng module → path chính (`path:line#anchor`) → trang wiki tương ứng›

| Module | Path chính | Trang wiki |
|---|---|---|
| ‹...› | ‹...› | ‹...› |

> Bảng router đầy đủ (vùng tác động → trang) nằm ở [`wiki/ROUTER.md`](wiki/ROUTER.md).

## 4. Vùng high-risk
‹đặc tả khi init — auth / payment / data migration / sync / third-party. Task đụng các vùng này bắt buộc đọc hết `mistakes` ACTIVE và thêm một vòng recall (xem `brain/RETRIEVAL.md`)›

## 5. Lệnh chạy / test / deploy local (đã xác nhận)
‹đặc tả khi init — chỉ ghi lệnh đã chạy thật và thấy pass, không đoán›

```bash
# build:
# test:
# lint:
# chạy local:
```

## 6. Vùng cấm đụng
‹đặc tả khi init — file/thư mục sinh tự động, vendor, secret, migration đã chạy production›

## 7. Cấu hình sub-agent của project
‹đặc tả khi init — lấy slot đang bật và model_verified=true từ Brain → Settings → Sub Agents; chỉ
ghi provider/model/vai trò đã smoke và lệnh verify để nhét vào spec; tuyệt đối không ghi credential›

Xem [`sub-agents/README.md`](sub-agents/README.md) để biết khi nào nên delegate.
