# emacs 風キーバインドにする
bindkey -e

# cmd+option+←/→ は herdr のタブ移動に使う（config/herdr/config.toml、ghostty/config）。
# herdr の外で押すと Ghostty が ESC[1;11D / ESC[1;11C を送り、割り当てがないと ;11D が入力行に入るので、
# 画面を描き直すだけの redisplay に割り当てて、何も起きないようにする。
bindkey '^[[1;11D' redisplay
bindkey '^[[1;11C' redisplay
