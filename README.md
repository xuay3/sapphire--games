# Sapphire 小组件订阅源

这份 JSON 就是组件里「订阅源」指向的文件。推到 GitHub 后开 Pages，把地址填进组件即可。

## 一、用 GitHub Pages 部署（推荐）

### 1. 建仓库

在 GitHub 新建一个 **public** 仓库，名字随意，例如 `sapphire-games`。

> 私有仓库要用 Pages 需要付费方案，所以建议 public。里面只有版本时间，没有隐私内容。

### 2. 推文件

把本目录下的这些文件推到仓库根目录：

```text
sapphire-games/
├─ games.json
├─ .nojekyll                       ← 让 Pages 不要跑 Jekyll
├─ tools/validate.py               ← 校验脚本
└─ .github/workflows/check.yml     ← 每天自动校验，数据过期变红提醒
```

用网页上传也行，命令行也行：

```bash
git init
git add .
git commit -m "add games.json"
git branch -M main
git remote add origin https://github.com/<你的用户名>/sapphire-games.git
git push -u origin main
```

### 3. 开 Pages

仓库 → **Settings → Pages**：

- Source 选 **Deploy from a branch**
- Branch 选 **main**，目录选 **/ (root)**
- 保存，等 1～2 分钟

### 4. 拿到地址

```text
https://<你的用户名>.github.io/sapphire-games/games.json
```

浏览器直接打开这个地址，应该能看到 JSON 内容。**这一步必须先用浏览器确认能打开**，否则组件里也拉不到。

### 5. 填进组件

组件右上角 ⚙ → 「订阅源（JSON 地址）」粘贴上面的地址 → 「立即同步」。
设置页「运行诊断」里「订阅同步」应该变成 `成功 <时间>`。

## 二、用 Gist 部署（更简单，但不好做自动校验）

1. 新建 gist，文件名 `games.json`，内容粘贴进去
2. 创建后点右上角 **Raw**
3. 地址形如 `https://gist.githubusercontent.com/<用户名>/<id>/raw/games.json`
4. 填进组件

缺点：Gist 没有 Pages，`/raw/` 地址在更新后会带 commit hash 变化吗？——用不带 hash 的 `/raw/games.json` 就始终指向最新版，没问题。但没有每天自动校验。

## 三、关于跨域

- `github.io` 和 `gist.githubusercontent.com` 都返回 `Access-Control-Allow-Origin: *`
- Sapphire 的 QML 组件走 Qt 的 `XMLHttpRequest`，本身不受浏览器 CORS 限制
- 所以两种方式在组件里都能拉

## 四、更新节奏

每期版本更新后改 `games.json`：

1. 改 `updatedAt`
2. 把 `version.end` 改成新版本的结束时间
3. 结束的卡池删掉或留着（组件会自动隐藏已结束的）
4. 新卡池追加到 `pools`
5. push

推上去后 GitHub Actions 会自动跑一次 `tools/validate.py`，有问题会在 Actions 页面标红；每天也会定时跑一次，数据过期（比如版本已结束但没更新）会再次变红提醒。

## 五、这套数据现在的内容

7 款游戏：原神、崩坏：星穹铁道、绝区零、鸣潮、明日方舟、明日方舟：终末地、无限暖暖。

字段含义与格式见上一级目录的 [`datasource/README.md`](../datasource/README.md)。
