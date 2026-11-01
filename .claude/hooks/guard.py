#!/usr/bin/env python3
"""
シェル経由の危険操作を実行前に止める PreToolUse フック（matcher: Bash）

設計: docs/design/guard_hook.md
仕様: docs/design/test_spec_guard_hook.md
【LES】移植元のコミット d20ea9a から複製した。LES の差分は「【LES】」で検索できる
【LES】（【LES】ブロック1か所と、行末に `# 【LES】` を付けた接続点だけ。移植元の関数・定数は書き換えていない）。
【LES】A の秘密に顧客データ（data/ 配下・*.db・*.sqlite*・*.xlsx）を含め、.env.development を外し、
【LES】読み取り動詞に sqlite3・unzip を足した（仕様 10節）

なぜ必要か:
  settings.json の permissions.deny（Read(**/.env) など）は Read ツールにしか効かず、
  Bash の `cat .env` は素通りする（移植元では、本物の .env の中身が会話に露出した）。【LES】

止めるもの（コマンド文字列だけで判定する）:
  A. 秘密ファイルの読み取り（.env・settings.local.json・鍵など）
  B. 保護対象（.claude/settings*.json・.claude/hooks/**・.claude そのもの）の書き換え・削除・移動
  C. 取り返しのつかない操作（git push --force・git reset --hard・rm -r * など）

方針:
- 相手は「善意の AI のうっかり」。意図的な回避（変数分割・エンコード）までは追わない
- 判定できないとき・guard 自身が壊れたときは通す（fail-open）。Bash が止まると
  セッション全体が使えなくなるため。最後の砦は人の承認と deny ルール
- ファイルを開かない・外部コマンドを起動しない（秘密を読む経路を guard 自身が作らないため）
- 標準ライブラリのみ。Python 3.10 以上
- 止めるときは exit 2 と stderr の理由。通すときは exit 0 で何も出さない
"""

import fnmatch
import json
import os
import posixpath
import re
import sys
from typing import Callable, NamedTuple

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

CATEGORY_SECRET = "秘密ファイルの読み取り"
CATEGORY_PROTECTED = "保護対象の書き換え"
CATEGORY_IRREVERSIBLE = "取り返しのつかない操作"

_ADVICE_HEAD = "回避を試みず、人に判断を求めてください。"
_ADVICE_TAIL = "誤検知と思われる場合は、そのことを人に伝えてください。"
ADVICE_SECRET = (
    f"{_ADVICE_HEAD}中身が必要なら人に確認してください"
    f"（Read/Grep ツールも deny ルールで止まります）。{_ADVICE_TAIL}"
)
ADVICE_PROTECTED = (
    f"{_ADVICE_HEAD}変更が必要なら Edit ツールで行う（承認ダイアログが出ます）か、"
    f"人に依頼してください。{_ADVICE_TAIL}"
)
ADVICE_IRREVERSIBLE = f"{_ADVICE_HEAD}必要なら人に実行してもらってください。{_ADVICE_TAIL}"

# $( ) / `` / bash -c / eval の入れ子の上限。悪意ある入れ子で再帰が深くならないように
MAX_DEPTH = 16
MAX_TARGET_CHARS = 200
# Linux の PATH_MAX。これより長い cd 先は bash でも失敗する
MAX_PATH_CHARS = 4096
# fnmatch は内部で正規表現にするので、長い glob を渡さない
MAX_GLOB_LEN = 64

# ---------------------------------------------------------------------------
# 語彙表（足すときはここだけ直せばよいようにデータで持つ）
# ---------------------------------------------------------------------------

# 中身を会話に出しうるコマンド（出力・コピー・送信・編集画面を含む）
READ_VERBS = frozenset("""
    cat tac nl less more most head tail grep egrep fgrep rg ag ack sed awk gawk
    cut sort uniq paste join diff comm od xxd hexdump strings base64 base32
    cp scp rsync tar zip gzip bat batcat view vi vim nvim nano emacs jq yq
    curl wget dd source .
""".split())

INTERPRETER_NAMES = frozenset({"node", "ruby", "perl", "php"})
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
RESERVED_WORDS = frozenset(
    "! { } if then else elif fi do done while until for in case esac select function".split()
)
# 次の語が関数名で、その後ろが本体になる予約語（function NAME { …; }）
FUNCTION_KEYWORD = "function"
# 後ろがコマンド（coproc cat x）か、名前＋{ 本体（coproc NAME { …; }）になる予約語
COPROC_KEYWORD = "coproc"
# coproc NAME の後ろに来る複合コマンドの始まり（bash はこの位置の予約語を予約語と読み、前の語を NAME にする）
COPROC_BODY_STARTS = frozenset("{ if while until for case select".split())

# 包み込みコマンド → 値を取るオプション（次の語も飛ばす）
WRAPPER_ARG_OPTIONS: dict[str, frozenset[str]] = {
    "sudo": frozenset({"-u", "-g", "-C", "-h", "-p", "-D", "-r", "-t", "-U"}),
    "env": frozenset({"-u"}),
    "command": frozenset(),
    "builtin": frozenset(),
    "exec": frozenset({"-a"}),
    "nohup": frozenset(),
    "time": frozenset(),
    "nice": frozenset({"-n"}),
    "timeout": frozenset({"-s", "-k"}),
    "xargs": frozenset({"-I", "-n", "-P", "-d", "-L", "-s", "-E", "-a"}),
}
FIND_EXEC_OPTIONS = frozenset({"-exec", "-execdir", "-ok", "-okdir"})

# .env.<x> のうち、見本として中身を共有してよいもの
SAFE_ENV_SUFFIXES = frozenset({"example", "sample", "template"})
KEY_PREFIXES = ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa")
BACKUP_DIR_NAME = "claude-settings-backup"

INPUT_REDIRECT_OPS = frozenset({"<", "<>"})
OUTPUT_REDIRECT_OPS = frozenset({">", ">>", ">|", "&>", "&>>", "<>", ">&"})
HEREDOC_OPS = frozenset({"<<", "<<-"})
# 最長一致の順に並べる
REDIRECT_OPS_LONGEST_FIRST = ("<<<", "<<-", "<<", "<>", "<&", "<", ">>", ">|", ">&", ">")

# rm -r の対象にすると作業ツリーやホームが丸ごと消えるもの
BROAD_LITERALS = frozenset({
    "/", "/*", "~", "~/", "~/*", "$HOME", "$HOME/", "$HOME/*",
    "*", ".", "./", "./*", "..", "../", "../*", ".*",
    "$CLAUDE_PROJECT_DIR", "$CLAUDE_PROJECT_DIR/", "$CLAUDE_PROJECT_DIR/*",
})
WHOLE_TREE_PATHS = frozenset({".", "./", ":/"})
GIT_ARG_OPTIONS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
# git push でリモートの ref を消す・丸ごと一致させる長いオプション（完全一致）
GIT_PUSH_DELETE_OPTIONS = frozenset({"--delete", "--mirror"})
# 未コミットの変更を捨てて切り替える長いオプション（完全一致。--force-create は -C の長い形なので含めない）
GIT_CHECKOUT_FORCE_OPTIONS = frozenset({"--force"})
GIT_SWITCH_FORCE_OPTIONS = frozenset({"--force", "--discard-changes"})
# 直後の文字列がブランチ名になる短いオプション。束の中でこの文字より後ろは読まない（-bfix の f は強制ではない）
GIT_CHECKOUT_VALUE_LETTERS = "bB"
GIT_SWITCH_VALUE_LETTERS = "cC"

# A1 で秘密パスとして数えない「除外の値」（9.3）。値は --exclude=値。完全一致
# 空白区切りの --exclude 値（次の語）は、下の OPTIONS_WITH_VALUE に表があるコマンドだけ割り引く
EXCLUDE_VALUE_COMMANDS = frozenset({"grep", "egrep", "fgrep", "rsync", "tar", "diff"})
EXCLUDE_VALUE_OPTIONS = frozenset({"--exclude", "--exclude-dir"})
# 9.3.1 値を取るオプション（値をくっつけていなければ次の語が値）。コマンド → (短いオプションの文字, 長いオプション)
# 前のオプションの値になった --exclude（grep -e --exclude .env）をオプションと読まないために使う。
# この表があるコマンドだけ空白区切りの --exclude 値を割り引く（rsync・tar は値つきオプションが版ごとに増え、
# 載せ忘れがそのまま穴になるので表を作らず `=` 形だけにする。9.9 決定2）。
# 値を省略できるもの（--color[=WHEN]・--context[=NUM]・--unified[=NUM]）は `=` でしか値を取らないので入れない
_GREP_VALUE_OPTIONS = ("efmABCdD", frozenset("""
    --regexp --file --max-count --after-context --before-context --context --directories --devices
    --label --binary-files --include --exclude --exclude-from --exclude-dir --group-separator
""".split()))
OPTIONS_WITH_VALUE: dict[str, tuple[str, frozenset[str]]] = {
    "grep": _GREP_VALUE_OPTIONS, "egrep": _GREP_VALUE_OPTIONS, "fgrep": _GREP_VALUE_OPTIONS,
    "diff": ("xXILFSDCUW", frozenset("""
        --exclude --exclude-from --ignore-matching-lines --label --show-function-line --starting-file
        --ifdef --width --tabsize --from-file --to-file --horizon-lines --palette --line-format
        --old-line-format --new-line-format --unchanged-line-format --old-group-format
        --new-group-format --changed-group-format --unchanged-group-format
    """.split())),
}
# 9.3 この環境変数があると GNU の getopt はオプションを並べ替えず、被演算子の後ろの --exclude・値を読む対象にする。
# 名前がコマンド文字列か字句解析後の語に現れたら、9.3・9.3.1 の割り引きをしない（大文字小文字を区別する）
POSIXLY_CORRECT_NAME = "POSIXLY_CORRECT"
# bash の POSIX モード（set -o posix・bash --posix・SHELLOPTS=posix）は POSIXLY_CORRECT=y を設定し、
# set -a（allexport）と組むと子の grep に渡る。名前が文字列に出ないので、語としての posix も同じ扱いにする
# （\b で区切るので posixly_correct には当たらない）
POSIX_MODE_PATTERN = re.compile(r"\bposix\b")

# 9.4「一覧だけ」のときに実行してよいコマンド（許可リスト。これ以外が1つでもあれば割り引かない）。
# 行は 名前を出すもの／名前を加工するだけのフィルタ／副作用の無いもの
LISTING_COMMANDS = frozenset("""
    find ls stat test [ [[
    sort uniq head tail grep egrep fgrep wc cut tr nl column cat
    echo printf cd pwd true false :
""".split())
# git はこのサブコマンドのときだけ許可リストに入り、被演算子を名前として割り引く
LISTING_GIT_SUBCOMMANDS = frozenset({"check-ignore", "ls-files", "status"})
# 被演算子が名前だけのコマンド（被演算子を割り引く）
NAME_ONLY_COMMANDS = frozenset({"ls", "stat", "test", "[", "[["})
# find の名前条件（次の語を割り引く）
FIND_NAME_OPTIONS = frozenset({"-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename",
                               "-regex", "-iregex"})
# 名前の一覧から中身を読むオプション（この文字列を含む語があれば割り引かない）
FILE_LIST_OPTIONS = ("--files0-from", "--files-from")
# 置換の目印（コマンド文字列のどこかにあれば割り引かない）
SUBSTITUTION_MARKS = ("$(", "`", "<(", ">(")

# 9.5 保護パスから外す使い捨て置き場（正規化した絶対パスの前置部分）
DISPOSABLE_DIRS = ("/tmp/", "/var/tmp/")
# 9.5 展開されると行き先が文字列から分からない目印（含むパスは使い捨て置き場として外さない）
UNKNOWN_PATH_MARKS = ("$", "{")
GLOB_CHARS = "*?["
# 9.5.1 find の、次の語に書き込むアクション（-fprintf FILE FORMAT も FILE は次の語）
FIND_OUTPUT_OPTIONS = frozenset({"-fprint", "-fprint0", "-fls", "-fprintf"})

# インラインコードを「語」に分けるための区切り文字（引用・括弧・演算子）
_CODE_SEPARATORS = str.maketrans({ch: " " for ch in "'\"`()[]{}=,;:+<>|&\t\n\r"})


# ---------------------------------------------------------------------------
# データモデル（NamedTuple: importlib でファイルから読み込んでも sys.modules に依存しない）
# ---------------------------------------------------------------------------

class Redirect(NamedTuple):
    op: str
    target: str  # クォート除去後
    # target に置換・$'…' をはめ込んだ（字句解析が置換の中身を取り除く・$'…' を簡略化して読むので、
    # 文字列が実際の行き先と違う）。xargs が走らせるシェルの中身も同じ印を付ける（_unknown_destination）。
    # 9.5 の使い捨て置き場の除外をしないために使う
    built: bool = False


class SimpleCommand(NamedTuple):
    words: tuple[str, ...]
    redirects: tuple[Redirect, ...]
    built: frozenset[int] = frozenset()  # 置換・$'…' をはめ込んだ語の添字（words 内）。Redirect.built と同じ意味


class Invocation(NamedTuple):
    name: str  # 包み込みを剥がした実際のコマンド（basename）
    args: tuple[str, ...]
    # "xargs"／"find": 引数の一部が外（標準入力・find の見つけたパス）から渡される
    via: str = ""


# ---------------------------------------------------------------------------
# 字句解析
#   shlex は $( )・バッククォート・ヒアドキュメントを知らないため手書きする。
#   位置は前にしか進まない（後戻りなし・O(n)）。正規表現は使わない。
# ---------------------------------------------------------------------------

class ParseError(Exception):
    """クォートや置換の閉じが無いなど、bash として読めない"""


class _CommandBuilder:
    """語と演算子を受け取り、区切りごとに SimpleCommand を作る"""

    def __init__(self, lexer: "_Lexer"):
        self._lexer = lexer
        self._words: list[str] = []
        self._redirects: list[Redirect] = []
        self._pending_op: str | None = None
        self._buf: list[str] = []
        self.in_word = False
        self._quoted = False
        self._built = False
        self._built_idx: list[int] = []

    def add(self, chars: str, quoted: bool = False) -> None:
        self._buf.append(chars)
        self.in_word = True
        self._quoted = self._quoted or quoted

    def mark_word(self, quoted: bool = False) -> None:
        """中身は足さないが、語がそこにあることだけ記録する（'' や $(…) の位置）"""
        self.in_word = True
        self._quoted = self._quoted or quoted

    def mark_built(self) -> None:
        """置換・$'…' をはめ込んだことを記録する（語の文字列が実際の値と違うことの印。9.5 条件2）"""
        self.mark_word()
        self._built = True

    def is_fd_number(self) -> bool:
        """直前に続いている語が `2>` の 2 のような fd 番号か"""
        if not self.in_word or self._quoted or not self._buf:
            return False
        return "".join(self._buf).isdigit()

    def discard_word(self) -> None:
        self._buf = []
        self.in_word = False
        self._quoted = False
        self._built = False

    def set_redirect(self, op: str) -> None:
        self._pending_op = op

    def end_word(self) -> None:
        if not self.in_word:
            return
        word = "".join(self._buf)
        built = self._built
        self.discard_word()
        if self._pending_op is None:
            if built:
                self._built_idx.append(len(self._words))
            self._words.append(word)
            return
        op = self._pending_op
        self._pending_op = None
        self._redirects.append(Redirect(op, word, built))
        if op in HEREDOC_OPS:
            self._lexer.pending_heredocs.append((word, op == "<<-"))

    def end_command(self) -> None:
        self.end_word()
        # リダイレクトの後に語が来なかった（`echo >` など）ものは捨てる
        self._pending_op = None
        if self._words or self._redirects:
            self._lexer.out.append(
                SimpleCommand(tuple(self._words), tuple(self._redirects), frozenset(self._built_idx)))
        self._words = []
        self._redirects = []
        self._built_idx = []


class _Lexer:
    def __init__(self, text: str):
        self.text = text
        self.n = len(text)
        self.pos = 0
        # 置換の中身も含め、見つかった単純コマンドをすべて平らに溜める
        self.out: list[SimpleCommand] = []
        # (区切り語, 先頭タブを除くか)。改行のたびに本文を読み飛ばす
        self.pending_heredocs: list[tuple[str, bool]] = []

    def parse_commands(self, depth: int, in_subst: bool) -> None:
        """単純コマンドの並びを読む。in_subst なら対応する `)` で戻る"""
        text = self.text
        b = _CommandBuilder(self)
        paren = 0  # 置換の中の ( ) の深さ（$((1+2)) のため）
        while True:
            if self.pos >= self.n:
                if in_subst:
                    raise ParseError("置換の閉じ括弧がありません")
                b.end_command()
                return
            c = text[self.pos]
            if c in " \t":
                b.end_word()
                self.pos += 1
            elif c == "\n":
                b.end_command()
                self.pos += 1
                self._skip_heredoc_bodies()
            elif c == "#" and not b.in_word:
                newline = text.find("\n", self.pos)
                self.pos = self.n if newline < 0 else newline
            elif c == "'":
                end = text.find("'", self.pos + 1)
                if end < 0:
                    raise ParseError("単一引用符が閉じていません")
                b.add(text[self.pos + 1:end], quoted=True)
                self.pos = end + 1
            elif c == '"':
                self.pos += 1
                self._read_double_quoted(b, depth)
            elif c == "\\":
                if self.pos + 1 < self.n and text[self.pos + 1] != "\n":
                    # `\;` は区切りではなく語 `;`（find -exec の終端）
                    b.add(text[self.pos + 1], quoted=True)
                self.pos += 2  # `\`改行は行継続なので何も足さない
            elif c == "$":
                self._read_dollar(b, depth, in_double_quote=False)
            elif c == "`":
                self._read_backtick(b, depth)
            elif c in "<>" and text.startswith("(", self.pos + 1):
                # プロセス置換 <( … ) / >( … ): 中身もコマンドとして判定する。語には中身が残らないので印を付ける
                self.pos += 2
                b.mark_built()
                self._enter_substitution(depth)
            elif c in "<>":
                self._read_redirect(b)
            elif c == "&" and text.startswith(">", self.pos + 1):
                b.end_word()
                op = "&>>" if text.startswith(">>", self.pos + 1) else "&>"
                self.pos += len(op)
                b.set_redirect(op)
            elif c in ";&|":
                # ; ;; ;& && & | || |& はどれも「ここでコマンドが切れる」点で同じ
                b.end_command()
                self.pos += 1
                while self.pos < self.n and text[self.pos] in ";&|":
                    self.pos += 1
            elif c == "(":
                b.end_command()
                paren += 1
                self.pos += 1
            elif c == ")":
                b.end_command()
                self.pos += 1
                if in_subst:
                    if paren == 0:
                        return
                    paren -= 1
            else:
                b.add(c)
                self.pos += 1

    def _enter_substitution(self, depth: int) -> None:
        if depth + 1 > MAX_DEPTH:
            raise ParseError("入れ子が深すぎます")
        # 同じ文字列・同じ位置から読む（中のヒアドキュメントや括弧の対応を正しく扱うため）
        self.parse_commands(depth + 1, in_subst=True)

    def _read_redirect(self, b: _CommandBuilder) -> None:
        if b.is_fd_number():
            b.discard_word()  # `2>` の 2 は引数ではない
        else:
            b.end_word()
        op = next(o for o in REDIRECT_OPS_LONGEST_FIRST if self.text.startswith(o, self.pos))
        self.pos += len(op)
        b.set_redirect(op)

    def _read_double_quoted(self, b: _CommandBuilder, depth: int) -> None:
        text = self.text
        b.mark_word(quoted=True)
        while True:
            if self.pos >= self.n:
                raise ParseError("二重引用符が閉じていません")
            c = text[self.pos]
            if c == '"':
                self.pos += 1
                return
            if c == "\\" and self.pos + 1 < self.n and text[self.pos + 1] in '$`"\\\n':
                if text[self.pos + 1] != "\n":
                    b.add(text[self.pos + 1], quoted=True)
                self.pos += 2
            elif c == "$":
                self._read_dollar(b, depth, in_double_quote=True)
            elif c == "`":
                self._read_backtick(b, depth)
            else:
                b.add(c, quoted=True)
                self.pos += 1

    def _read_dollar(self, b: _CommandBuilder, depth: int, in_double_quote: bool) -> None:
        text = self.text
        nxt = text[self.pos + 1] if self.pos + 1 < self.n else ""
        if nxt == "(":
            self.pos += 2
            # 置換の中身は外側の語に足さない（ヒアドキュメント本文が外に混ざらないように）。
            # そのため語の文字列は実際の値と違うので印を付ける（$(( … )) もここを通る）
            b.mark_built()
            self._enter_substitution(depth)
        elif nxt == "{":
            end = text.find("}", self.pos + 2)
            if end < 0:
                raise ParseError("${ が閉じていません")
            # 展開しない。$HOME・$CLAUDE_PROJECT_DIR の判定に文字どおり使う
            b.add(text[self.pos:end + 1])
            self.pos = end + 1
        elif nxt == "'" and not in_double_quote:
            # $'…'（ANSI-C 引用）。エスケープは「次の1文字をそのまま」に簡略化する
            i = self.pos + 2
            chars: list[str] = []
            while i < self.n and text[i] != "'":
                if text[i] == "\\" and i + 1 < self.n:
                    chars.append(text[i + 1])
                    i += 2
                else:
                    chars.append(text[i])
                    i += 1
            if i >= self.n:
                raise ParseError("$' が閉じていません")
            b.add("".join(chars), quoted=True)
            b.mark_built()  # 簡略化して読んだので、文字列が実際の値と違いうる
            self.pos = i + 1
        else:
            b.add("$")
            self.pos += 1

    def _read_backtick(self, b: _CommandBuilder, depth: int) -> None:
        text = self.text
        i = self.pos + 1
        chars: list[str] = []
        while True:
            if i >= self.n:
                raise ParseError("バッククォートが閉じていません")
            ch = text[i]
            if ch == "\\" and i + 1 < self.n and text[i + 1] in "`\\$":
                chars.append(text[i + 1])
                i += 2
                continue
            if ch == "`":
                break
            chars.append(ch)
            i += 1
        if depth + 1 > MAX_DEPTH:
            raise ParseError("入れ子が深すぎます")
        self.out.extend(parse("".join(chars), depth + 1))
        b.mark_built()
        self.pos = i + 1

    def _skip_heredoc_bodies(self) -> None:
        """改行の直後に、保留中のヒアドキュメント本文を読み飛ばす（本文はデータであってコマンドではない）"""
        text = self.text
        while self.pending_heredocs:
            delimiter, strip_tabs = self.pending_heredocs.pop(0)
            while self.pos < self.n:
                newline = text.find("\n", self.pos)
                line_end = self.n if newline < 0 else newline
                line = text[self.pos:line_end]
                self.pos = self.n if newline < 0 else newline + 1
                if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                    break


def parse(text: str, depth: int = 0) -> list[SimpleCommand]:
    """bash のコマンド文字列を単純コマンドの平らなリストにする。読めなければ ParseError"""
    lexer = _Lexer(text)
    lexer.parse_commands(depth, in_subst=False)
    return lexer.out


def parse_lenient(text: str, depth: int = 0) -> list[SimpleCommand]:
    """全体が読めなければ行ごとに読み、読めた行だけ返す（bash は行ごとに実行するので前の行は実際に走る）"""
    try:
        return parse(text, depth)
    except ParseError:
        pass
    result: list[SimpleCommand] = []
    for line in text.split("\n"):
        try:
            result.extend(parse(line, depth))
        except ParseError:
            continue
    return result


# ---------------------------------------------------------------------------
# 実際に走るコマンドを取り出す
# ---------------------------------------------------------------------------

def _is_assignment(word: str) -> bool:
    name, sep, _ = word.partition("=")
    if not sep or not name:
        return False
    if not (name[0].isalpha() or name[0] == "_"):
        return False
    return all(ch.isalnum() or ch == "_" for ch in name)


def _skip_wrapper_options(words: list[str], i: int, wrapper: str) -> int:
    arg_options = WRAPPER_ARG_OPTIONS[wrapper]
    while i < len(words):
        word = words[i]
        if wrapper == "env" and _is_assignment(word):
            i += 1
        elif word.startswith("-") and word != "-":
            i += 2 if word in arg_options else 1
        else:
            break
    if wrapper == "timeout" and i < len(words):
        i += 1  # 秒数
    return i


def _strip_wrappers(words: list[str]) -> Invocation | None:
    """先頭の代入・予約語・包み込み（sudo・env・xargs など）を剥がす"""
    i = 0
    via = ""
    while i < len(words):
        word = words[i]
        # 名前を取る予約語は、後ろの名前をコマンド名と取り違えないよう名前ごと剥がす（本体を判定に掛けるため）。
        # RESERVED_WORDS の判定より前に置く（function は RESERVED_WORDS にも入っていて、1語だけ剥がすのが先に効くため）
        if word == FUNCTION_KEYWORD:
            i += 2  # function と関数名。後ろの `{` は予約語として次の周で剥がれる
            continue
        if word == COPROC_KEYWORD:
            # coproc NAME { … }・coproc NAME if/while … のときだけ NAME も剥がす。coproc cat x は cat がコマンド
            i += 2 if i + 2 < len(words) and words[i + 2] in COPROC_BODY_STARTS else 1
            continue
        if _is_assignment(word) or word in RESERVED_WORDS:
            i += 1
            continue
        name = word.rsplit("/", 1)[-1] or word
        if name in WRAPPER_ARG_OPTIONS:
            if name == "xargs":
                via = "xargs"
            i = _skip_wrapper_options(words, i + 1, name)
            continue
        return Invocation(name, tuple(words[i + 1:]), via)
    return None


def invocations(cmd: SimpleCommand) -> list[Invocation]:
    words = list(cmd.words)
    first = _strip_wrappers(words)
    if first is None:
        return []
    result = [first]
    if first.name == "find":
        # find … -exec CMD … ; の CMD も実際に走るコマンド
        args = first.args
        i = 0
        while i < len(args):
            if args[i] in FIND_EXEC_OPTIONS:
                j = i + 1
                while j < len(args) and args[j] not in (";", "+"):
                    j += 1
                inner = _strip_wrappers(list(args[i + 1:j]))
                if inner is not None:
                    result.append(inner._replace(via="find"))
                i = j
            i += 1
    return result


def _shell_inline_code(args: tuple[str, ...]) -> str | None:
    """bash -c 'CODE' の CODE。最初の被演算子より前の、c を含む短いオプション束の次の語"""
    i = 0
    while i < len(args):
        word = args[i]
        if word in ("-o", "+o"):
            i += 2
            continue
        if not word.startswith(("-", "+")) or word in ("-", "--"):
            return None
        if word.startswith("-") and not word.startswith("--") and "c" in word[1:]:
            return args[i + 1] if i + 1 < len(args) else None
        i += 1
    return None


def _unknown_destination(cmd: SimpleCommand) -> SimpleCommand:
    """語・リダイレクトのすべてに J1 の印を付けた写し（xargs が走らせるシェルの中身。-I の置き換えで行き先が文字列と違う）"""
    return cmd._replace(built=frozenset(range(len(cmd.words))),
                        redirects=tuple(r._replace(built=True) for r in cmd.redirects))


def collect(command: str, depth: int = 0) -> list[SimpleCommand]:
    """bash -c・eval の中身まで展開して、単純コマンドを平らに集める"""
    cmds = parse_lenient(command, depth)
    if depth + 1 >= MAX_DEPTH:
        return cmds
    # 展開した中身は親のすぐ後ろに置く（cd の前後関係で判定する規則があるため、実行順を保つ）
    result: list[SimpleCommand] = []
    for cmd in cmds:
        result.append(cmd)
        invs = invocations(cmd)
        # xargs が走らせるのは先頭の Invocation だけ（find -exec の中は via が "find" で上書きされる）。
        # そのため xargs -I X find . -exec sh -c '…/tmp/X/…' \; の sh も、先頭で xargs かどうかを見る
        from_xargs = bool(invs) and invs[0].via == "xargs"
        for inv in invs:
            code = None
            if inv.name in SHELLS:
                code = _shell_inline_code(inv.args)
            elif inv.name == "eval":
                # `eval eval … cmd` を1段ずつ展開すると入れ子の上限で止まり、
                # 段数ぶん全体を解析し直して遅くなるので、続く eval はまとめて剥がす
                start = 0
                while start < len(inv.args) and inv.args[start] == "eval":
                    start += 1
                code = " ".join(inv.args[start:])
            if code:
                inner = collect(code, depth + 1)
                if from_xargs:
                    # xargs -I X sh -c 'rm /tmp/X/…' は置き換え文字列が中身に入る。中から xargs の出どころが見えなくなるので、
                    # ここで中身のすべての書き込み先を「行き先が文字列で決まらない」にする（9.5「xargs には当てない」）
                    inner = [_unknown_destination(c) for c in inner]
                result.extend(inner)
    return result


# ---------------------------------------------------------------------------
# パスの判定（文字列だけ。ファイル・環境を見ない）
# ---------------------------------------------------------------------------

def _strip_value_prefix(word: str) -> str:
    """`if=`・`--env-file=` と先頭の `@` を外す（path_components と is_disposable_path で読み方をそろえる）"""
    name, sep, rest = word.partition("=")
    if sep and name and all(ch.isalnum() or ch in "_-" for ch in name):
        word = rest
    if word.startswith("@"):
        word = word[1:]
    return word


def path_components(word: str) -> list[str]:
    """`if=`・`--env-file=`・`@` を外し、/ で分けた構成要素（`.`・`..`・空は捨てる）"""
    return [part for part in _strip_value_prefix(word).split("/") if part not in ("", ".", "..")]


def is_secret_path(word: str) -> bool:
    # 大文字小文字を区別しないファイルシステム（WSL の /mnt/c など）では `.ENV` でも同じファイルが読める
    comps = path_components(word.lower())
    if not comps:
        return False
    base = comps[-1]
    if base == ".env":
        return True
    if base.startswith(".env."):
        # 未知の名前（.env.prod2）は秘密の側に倒す
        return base[5:].split(".")[0] not in SAFE_ENV_SUFFIXES
    if base == "settings.local.json":
        return True
    if base.endswith(".pem") or base.startswith(KEY_PREFIXES):
        return True
    if BACKUP_DIR_NAME in comps:
        return True
    # bash は `*` でドットファイルを展開しないが、`.e*`・`.*` は .env に一致しうる
    if base.startswith(".") and any(ch in base for ch in "*?[") and len(base) <= MAX_GLOB_LEN:
        return fnmatch.fnmatchcase(".env", base)
    return False


def is_disposable_path(word: str, project_dir: str | None, literal: bool = True) -> bool:
    """9.5。/tmp/・/var/tmp/ の下で、プロジェクトの下ではない絶対パス（$・{ を含まない）

    正規化してから比べる（/tmp/../<プロジェクト> で戻る形を外さないため）。
    $（変数）・{（ブレース展開。/tmp/{a,../x} は文字列の正規化と展開後の行き先が違う）を含むものは
    中身が分からないので外さない。
    literal は「語の文字列が実際の行き先そのものか」。False（置換・$'…' をはめ込んだ語＝J1、xargs を経た書き込み先＝9.10）
    は、文字列から行き先を決められないので外さない。
    """
    if not literal:
        return False
    p = _strip_value_prefix(word)
    if any(mark in p for mark in UNKNOWN_PATH_MARKS) or not p.startswith("/"):
        return False
    # . で始まるグロブ（.?・.*・.[.]）は bash によっては .. に当たり、文字列の正規化と行き先がずれる
    if any(part.startswith(".") and any(ch in part for ch in GLOB_CHARS) for part in p.split("/")):
        return False
    n = "/" + posixpath.normpath(p).lstrip("/")  # normpath は先頭の // を残すので揃える
    if not n.startswith(DISPOSABLE_DIRS):
        return False
    if project_dir and project_dir.startswith("/"):
        # プロジェクトが /tmp の下にある（テストの tmp_path など）ときは、プロジェクトの .claude を守る
        proj = "/" + posixpath.normpath(project_dir).lstrip("/")
        if n == proj or n.startswith(proj + "/"):
            return False
    return True


def is_protected_path(word: str, project_dir: str | None = None, literal: bool = True) -> bool:
    # 書き込み先の判定はすべてここを通るので、使い捨て置き場の除外もここ1か所に置く（呼び出し側ごとに足すと漏れる）。
    # 構造の判定（下）は literal に関係なく行う
    if is_disposable_path(word, project_dir, literal):
        return False
    comps = path_components(word)
    for i, comp in enumerate(comps):
        # 部分一致にしない（.claude-notes・docs/claude は対象外）
        if comp != ".claude":
            continue
        if i == len(comps) - 1:
            return True
        nxt = comps[i + 1]
        if nxt == "hooks":
            return True
        if i + 1 == len(comps) - 1 and nxt.startswith("settings") and nxt.endswith(".json"):
            return True
    return False


def _split_anchor(t: str) -> tuple[str, str]:
    """パスを (起点, 残り) に分ける。起点は "/"・"~"・"$CLAUDE_PROJECT_DIR"・"."（作業ディレクトリ）"""
    if t.startswith("/"):
        return "/", t
    for anchor in ("~", "$HOME", "$CLAUDE_PROJECT_DIR", "$PWD"):
        if t == anchor or t.startswith(anchor + "/"):
            key = {"$HOME": "~", "$PWD": "."}.get(anchor, anchor)
            return key, t[len(anchor):].lstrip("/")
    return ".", t


def _covers(path: str, project_dir: str) -> bool:
    """絶対パス path がプロジェクト自身かその祖先（/home・/home/user など。【LES】例のユーザー名を置き換えた）か"""
    b = "/" + posixpath.normpath(path).lstrip("/")  # normpath は先頭の // を残すので揃える
    p = posixpath.normpath(project_dir)
    return b == "/" or p == b or p.startswith(b + "/")


def is_broad_target(word: str, project_dir: str | None) -> bool:
    """rm -r の対象として広すぎるか。`./.`・`~/.`・`../..` のような書き方の違いも正規化して見る

    相対パスは作業ディレクトリ＝プロジェクトとみなす（Bash ツールの既定。cd 後は誤検知の側に倒れる）。
    ~ の実体（HOME）は見ない（環境を判定材料にしないため）。
    """
    t = word
    for alias, canon in (("${HOME}", "$HOME"), ("${CLAUDE_PROJECT_DIR}", "$CLAUDE_PROJECT_DIR"),
                         ("${PWD}", "$PWD")):
        t = t.replace(alias, canon)
    if t in BROAD_LITERALS:  # `*`・`.*` など glob はここで決める
        return True
    if not t:
        return False  # `"$(mktemp -d)"` のように置換だけの語は中身が分からないので通す
    if t.endswith("/*"):
        t = t[:-2] or "/"
    anchor, rest = _split_anchor(t)
    if "$" in rest:
        return False  # 未知の変数（"$dir"/x）は判定できないので通す
    has_project = bool(project_dir) and project_dir.startswith("/")
    if anchor == "/":
        return _covers(rest, project_dir) if has_project else posixpath.normpath(rest) in ("/", "//")
    if has_project and anchor in (".", "$CLAUDE_PROJECT_DIR"):
        return _covers(posixpath.join(project_dir, rest), project_dir)
    # 起点の実体が分からない: 起点そのものか、それより上だけを広いとみなす
    return all(part == ".." for part in posixpath.normpath(rest or ".").split("/") if part != ".")


# ===========================================================================
# 【LES】移植元のコミット d20ea9a からの差分（ここから）
#   移植元の関数・定数は書き換えない。差分はこのブロックと、行末に `# 【LES】` を付けた接続点だけ。
#   仕様: docs/design/test_spec_guard_hook.md 10節（L1〜L6・V）
# ===========================================================================

# V: 読み取り動詞に足す（9.3 の除外の値・9.4 の一覧だけには足さない。7節-21）
LES_READ_VERBS = frozenset({"sqlite3", "unzip"})
# L1〜L3: 顧客 DB・出力の Excel（小文字にした basename で比べる）
LES_CUSTOMER_FILE_ENDINGS = (".db", ".xlsx")
LES_CUSTOMER_FILE_INFIX = ".sqlite"
# L4: glob のリテラルの `.` より後ろがこれに一致しうれば顧客ファイル（sqlite… は代表の綴りで見る）
LES_CUSTOMER_GLOB_SAMPLES = ("db", "xlsx", "sqlite", "sqlite3")
# L5: 顧客データの置き場所（プロジェクト直下の data/ だけ）
LES_CUSTOMER_DATA_DIR = "data"
LES_PROJECT_DIR_VARS = ("$claude_project_dir", "${claude_project_dir}")  # 小文字にした後で比べる
# L5（決定11）: `..` を解くときに残す前置部分（小文字にした後で比べる。先頭の `/` は normpath が残す）
LES_PATH_ANCHORS = ("~", "$home", "${home}") + LES_PROJECT_DIR_VARS
# L6: basename がちょうどこれなら .env.* の規則から外す（.env.development.local は外さない）
LES_ENV_EXCEPTIONS = frozenset({".env.development"})


def les_is_customer_file(base: str) -> bool:
    """L1〜L4。base は小文字の basename"""
    if base.endswith(LES_CUSTOMER_FILE_ENDINGS) or LES_CUSTOMER_FILE_INFIX in base:
        return True
    # 長い glob は fnmatch に渡さない（移植元の is_secret_path と同じ理由）
    if not any(ch in base for ch in GLOB_CHARS) or len(base) > MAX_GLOB_LEN:
        return False
    # 見本の拡張子は `.` を含まないので、最後の `.` より後ろだけ見れば足りる（`*.*`・`clients.d?` を拾う）
    _, dot, suffix = base.rpartition(".")
    return bool(dot) and any(fnmatch.fnmatchcase(sample, suffix) for sample in LES_CUSTOMER_GLOB_SAMPLES)


def les_resolve_dotdot(raw: str) -> str:
    """L5（決定11）。前置部分を残し、`.` と `名前/..` を打ち消した形。前置部分より前に戻らず、相対パスの先頭に余った `..` は残す"""
    # normpath だけだと ~/../data/x が data/x になり、~ の親の data/ をプロジェクト直下と取り違える（仕様 3.3）
    anchor, sep, rest = raw.partition("/")
    if sep and anchor in LES_PATH_ANCHORS:
        return anchor + "/" + posixpath.normpath(rest)
    return posixpath.normpath(raw)


def les_is_customer_data_dir(word: str, project_dir: str | None, in_code: bool) -> bool:
    """L5。word は小文字。先頭側で判定する（.gitignore の /data/ と同じく、直下の data/ だけを指すため）。
    書いたままの形と `..` を解いた形のどちらかで当たれば真（11節 決定11）"""
    if in_code and "/" not in word:
        return False  # A3 では Python の変数名 data を数えない（11節 決定1）
    raw = _strip_value_prefix(word)
    # 書いたままの形は置き換えずに残す（data/../src/a.py・/work/proj/../data/x を通さないため。7節-23）。
    # 2つの形を OR で掛けるので、解いた形を足しても止める側にしか動かない
    forms = [(raw, path_components(word))]
    if ".." in raw:
        resolved = les_resolve_dotdot(raw)
        forms.append((resolved, path_components(resolved)))
    name = posixpath.basename(posixpath.normpath(project_dir)).lower() if project_dir else None
    for form, comps in forms:
        if not comps:
            continue
        # ① 相対パスの最初の構成要素（`.`・`..` は path_components が捨てている）
        if not form.startswith(("/", "~", "$")) and comps[0] == LES_CUSTOMER_DATA_DIR:
            return True
        # ② $CLAUDE_PROJECT_DIR の直後
        if comps[0] in LES_PROJECT_DIR_VARS and comps[1:2] == [LES_CUSTOMER_DATA_DIR]:
            return True
        # ③ プロジェクトのフォルダ名の直後（/work/proj/data/x・~/pjt/proj/data/x・../proj/data/x）
        if name and any(a == name and b == LES_CUSTOMER_DATA_DIR for a, b in zip(comps, comps[1:])):
            return True
    return False


def les_is_secret_path(word: str, project_dir: str | None = None, in_code: bool = False) -> bool:
    """移植元の is_secret_path に L1〜L6 を重ねる。A1〜A3 の秘密パスの判定はすべてここを通る"""
    w = word.lower()
    comps = path_components(w)
    if comps and les_is_customer_file(comps[-1]):
        return True
    if les_is_customer_data_dir(w, project_dir, in_code):
        return True
    if comps and comps[-1] in LES_ENV_EXCEPTIONS:
        # basename の規則（.env.*）だけを外し、構成要素の規則（退避フォルダ）は親のパスで移植元の判定に掛ける。
        # 「偽を返す」にすると、移植元が将来足す構成要素の規則まで打ち消してしまう（11節 決定10）
        return is_secret_path(posixpath.dirname(_strip_value_prefix(word)))
    return is_secret_path(word)

# 【LES】差分（ここまで）


# ---------------------------------------------------------------------------
# 規則
# ---------------------------------------------------------------------------

def bundle_letters(word: str) -> str:
    """`-rfv` → `rfv`、`-i.bak` → `i`。`--long` と `-` だけは空"""
    if not word.startswith("-") or word.startswith("--"):
        return ""
    letters = []
    for ch in word[1:]:
        if not ch.isalpha():
            break
        letters.append(ch)
    return "".join(letters)


def letters_before_value(word: str, value_letters: str) -> str:
    """bundle_letters(word) を、value_letters のどれかが最初に現れた位置（その文字を含む）で切る。
    `-fb` → "fb"、`-bfix/x` → "b"、`-cfeature` → "c"、`-fq` → "fq"、`--force` → ""

    値を取る短いオプションの後ろは値（ブランチ名）なので、そこに f があっても強制ではない。
    """
    letters = bundle_letters(word)
    for i, ch in enumerate(letters):
        if ch in value_letters:
            return letters[:i + 1]
    return letters


def operands(args: tuple[str, ...]) -> list[str]:
    return [a for a in args if not a.startswith("-")]


def _is_interpreter(name: str) -> bool:
    if name.startswith("python"):
        return all(ch.isdigit() or ch == "." for ch in name[len("python"):])
    return name in INTERPRETER_NAMES


def _interpreter_inline_code(args: tuple[str, ...]) -> str | None:
    """python3 -c CODE / node -e CODE。スクリプト名より後の -e はスクリプト側の引数なので見ない"""
    for i, word in enumerate(args):
        if not word.startswith("-"):
            return None
        letters = bundle_letters(word)
        if "c" in letters or "e" in letters:
            return args[i + 1] if i + 1 < len(args) else None
    return None


def _takes_next_value(word: str, value_options: tuple[str, frozenset[str]]) -> bool:
    """word が値をくっつけていない「値を取るオプション」か（次の語がその値になるか）。9.3.1

    長い: 表と完全一致（`=` を含む語は値をくっつけているので当たらない）。
    短い束: 左から読み、値を取る文字が最初に現れた位置で決める（getopt と同じ）。
            それが束の最後なら次の語が値（`-e`・`-ve`）、後ろに文字が続けばそれが値（`-A3`・`-ev`）。
    """
    letters, long_options = value_options
    if word.startswith("--"):
        return word in long_options
    if not word.startswith("-") or word == "-":
        return False
    body = word[1:]
    for k, ch in enumerate(body):
        if ch in letters:
            return k == len(body) - 1
    return False


def _exclude_value_positions(name: str, args: tuple[str, ...]) -> list[int]:
    """9.3。args の中で --exclude／--exclude-dir の値になっている語の添字（args 内）。

    左から1回読み、前のオプションの値になった語はオプションとして読まずに飛ばす（9.3.1。
    `grep -e --exclude .env` の .env は読む対象。`=` 形も同じ規則で、値なら割り引かない）。
    `--` で読むのを止める（`--` の後ろはパターンと読む対象で、オプションではない）。
    完全一致・`名前=` の前置一致だけを見るので、--exclude-from=・--include= は当たらない（数え続ける）。
    """
    value_options = OPTIONS_WITH_VALUE.get(name)  # None なら rsync・tar（空白区切りを割り引かない）
    positions = []
    i = 0
    while i < len(args):
        word = args[i]
        if word == "--":
            break
        if value_options is not None and word in EXCLUDE_VALUE_OPTIONS:
            if i + 1 < len(args):
                positions.append(i + 1)
            i += 2
        elif any(word.startswith(option + "=") for option in EXCLUDE_VALUE_OPTIONS):
            positions.append(i)
            i += 1
        elif value_options is not None and _takes_next_value(word, value_options):
            i += 2  # 次の語はこのオプションの値。--exclude でもオプションとして読まない
        else:
            i += 1
    return positions


def _name_positions(name: str, args: tuple[str, ...]) -> list[int]:
    """9.4。名前として扱われる語の添字（args 内）。中身を出さないコマンドの被演算子と find の名前条件の値"""
    if name in NAME_ONLY_COMMANDS:
        return [i for i, word in enumerate(args) if not word.startswith("-")]
    if name == "git":
        sub, rest = split_git(args)
        if sub not in LISTING_GIT_SUBCOMMANDS:
            return []
        # rest は args の末尾側の切り出しなので、添字をずらせば args 内の位置になる
        offset = len(args) - len(rest)
        return [offset + i for i, word in enumerate(rest) if not word.startswith("-")]
    if name == "find":
        return [i + 1 for i, word in enumerate(args) if word in FIND_NAME_OPTIONS and i + 1 < len(args)]
    return []


def _has_empty_parens(text: str) -> bool:
    """`(` の後に空白・タブだけをはさんで `)` が続く箇所があるか（`ls() {`・`ls ( ) {` の関数定義の目印）"""
    i = text.find("(")
    while i != -1:
        j = i + 1
        while j < len(text) and text[j] in " \t":
            j += 1
        if j < len(text) and text[j] == ")":
            return True
        i = text.find("(", i + 1)
    return False


def is_listing_only(cmds: list[SimpleCommand], command: str) -> bool:
    """9.4。見つけた・並べた名前が、中身を読むコマンドの対象になる経路が無いか。コマンド全体で1回だけ計算する

    許可リスト方式にする（読む経路を禁止リストで並べると漏れが新しい穴になる。知らないコマンドは止める側に倒す）。
    """
    # 行継続を外してから見る（`$\<改行>(` は bash では置換だが、字句解析は置換と読まない）
    text = command.replace("\\\n", "")
    if any(mark in text for mark in SUBSTITUTION_MARKS):
        return False
    # 関数定義は「名前で中身が決まる」という許可リストの前提を崩す（ls() { cat "$@"; }; ls .env）
    if _has_empty_parens(text):
        return False
    for cmd in cmds:
        # 先頭の語に限らない（! function ls {・then function ls {・time function ls { も関数定義）
        if FUNCTION_KEYWORD in cmd.words:
            return False
        if any(option in word for word in cmd.words for option in FILE_LIST_OPTIONS):
            return False
        invs = invocations(cmd)
        # 包み込みだけで終わる形（xargs -a FILE）は何が走るか分からない
        if not invs and any(not _is_assignment(w) and w not in RESERVED_WORDS for w in cmd.words):
            return False
        for inv in invs:
            if inv.via:  # xargs・find -exec の中は、名前が外から渡される
                return False
            if inv.name == "git":
                if split_git(inv.args)[0] not in LISTING_GIT_SUBCOMMANDS:
                    return False
            elif inv.name not in LISTING_COMMANDS:
                return False
            if inv.name == "find" and any(a in FIND_EXEC_OPTIONS for a in inv.args):
                return False
    return True


def _mentions_posixly_correct(cmds: list[SimpleCommand], command: str) -> bool:
    """生のコマンド文字列、または字句解析後の語・リダイレクトの対象のどれかに名前が含まれるか（位置は問わない）

    効く位置（代入の前置き・env・export の後など）は読み分けない。読み分けの漏れがそのまま穴になるため（9.3）。
    字句解析後の語も見るのは、引用や \\ で生の文字列の名前が切れる形（env "POSIXLY_"CORRECT=1 …）を拾うため。
    bash の POSIX モードを指す語 posix（set -a; set -o posix; grep …）も同じに数える。
    """
    texts = [command, *(w for cmd in cmds for w in cmd.words), *(r.target for cmd in cmds for r in cmd.redirects)]
    return any(POSIXLY_CORRECT_NAME in t or POSIX_MODE_PATTERN.search(t) for t in texts)


def _uncounted_positions(cmd: SimpleCommand, listing_only: bool, discount_excludes: bool) -> frozenset[int]:
    """A1 で数えない cmd.words の添字

    語の役割は包み込みを剥がした後の最初の Invocation で決める。その args は cmd.words の末尾側の切り出しなので、
    len(words) - len(args) を足せば words 内の位置になる（find -exec の中の Invocation は途中の切り出しなので使わない）。
    """
    first = _strip_wrappers(list(cmd.words))
    if first is None:
        return frozenset()
    positions: list[int] = []
    if discount_excludes and first.name in EXCLUDE_VALUE_COMMANDS:
        positions.extend(_exclude_value_positions(first.name, first.args))
    if listing_only:
        positions.extend(_name_positions(first.name, first.args))
    offset = len(cmd.words) - len(first.args)
    return frozenset(offset + k for k in positions)


def find_secret_read(cmds: list[SimpleCommand], command: str, project_dir: str | None = None) -> str | None:  # 【LES】
    """秘密の読み取りに当たった対象を返す"""
    # A2: 入力リダイレクト（動詞を問わない）
    for cmd in cmds:
        for r in cmd.redirects:
            if r.op in INPUT_REDIRECT_OPS and les_is_secret_path(r.target, project_dir):  # 【LES】
                return r.target

    invs = [inv for cmd in cmds for inv in invocations(cmd)]

    # A3: インタプリタのインラインコードの中の語
    for inv in invs:
        if not _is_interpreter(inv.name):
            continue
        code = _interpreter_inline_code(inv.args)
        if code is None:
            continue
        for token in code.translate(_CODE_SEPARATORS).split():
            if les_is_secret_path(token, project_dir, in_code=True):  # 【LES】
                return token

    # A1: 読み取り動詞と秘密パスが同じコマンド全体にある（`F=.env; cat $F` を拾うため単純コマンドをまたぐ）
    if not any(inv.name in READ_VERBS or inv.name in LES_READ_VERBS for inv in invs):  # 【LES】
        return None
    # 除外の値・一覧だけの名前は読む対象ではないので、語の位置で外す（同じ文字列が被演算子にもあれば数える）
    listing_only = is_listing_only(cmds, command)  # 動詞があるときだけ・1回だけ（二乗にしない）
    discount_excludes = not _mentions_posixly_correct(cmds, command)  # 同じく1回だけ
    for cmd in cmds:
        uncounted = _uncounted_positions(cmd, listing_only, discount_excludes)
        for i, word in enumerate(cmd.words):
            if i not in uncounted and les_is_secret_path(word, project_dir):  # 【LES】
                return word
        for r in cmd.redirects:
            if r.op in HEREDOC_OPS or r.op == "<<<":
                continue
            if les_is_secret_path(r.target, project_dir):  # 【LES】
                return r.target
    return None


def _copy_like_targets(args: tuple[str, ...]) -> list[str]:
    """cp・rsync・install・ln の書き込み先（-t DIR か最後の被演算子）"""
    for i, word in enumerate(args):
        if word == "-t" and i + 1 < len(args):
            return [args[i + 1]]
        if word.startswith("--target-directory="):
            return [word.split("=", 1)[1]]
        if word.startswith("-t") and not word.startswith("--") and len(word) > 2:
            return [word[2:]]
    ops = operands(args)
    return ops[-1:]


def _dd_targets(args: tuple[str, ...]) -> list[str]:
    return [a[3:] for a in args if a.startswith("of=")]


def _sed_targets(args: tuple[str, ...]) -> list[str]:
    in_place = any(a.startswith("--in-place") or "i" in bundle_letters(a) for a in args)
    return operands(args) if in_place else []


def _perl_targets(args: tuple[str, ...]) -> list[str]:
    in_place = any("i" in bundle_letters(a) for a in args)
    return operands(args) if in_place else []


def split_git(args: tuple[str, ...]) -> tuple[str | None, tuple[str, ...]]:
    """git のグローバルオプション（-C x など）を越えて (サブコマンド, 残り) を返す"""
    i = 0
    while i < len(args):
        word = args[i]
        if word in GIT_ARG_OPTIONS:
            i += 2
        elif word.startswith("-"):
            i += 1
        else:
            return word, args[i + 1:]
    return None, ()


def _git_work_dir(args: tuple[str, ...]) -> str:
    """`git -C DIR` の DIR（複数あればつなぐ）。無ければ空"""
    base = ""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            base = posixpath.join(base, args[i + 1])
        i += 2 if args[i] in GIT_ARG_OPTIONS else 1
    return base


def _git_targets(args: tuple[str, ...]) -> list[str]:
    sub, rest = split_git(args)
    if sub not in ("mv", "rm"):
        return []
    # git -C .claude/hooks rm guard.py の guard.py は .claude/hooks/guard.py のこと
    base = _git_work_dir(args)
    return [posixpath.join(base, t) if base and _is_relative(t) else t for t in operands(rest)]


def _all_operands(args: tuple[str, ...]) -> list[str]:
    return operands(args)


def _find_targets(args: tuple[str, ...]) -> list[str]:
    """9.5.1。-fprint／-fprint0／-fls／-fprintf の次の語（探し始める場所は書き込み先ではない）"""
    return [args[i + 1] for i, word in enumerate(args) if word in FIND_OUTPUT_OPTIONS and i + 1 < len(args)]


# コマンド名 → 書き込み先の取り出し方。コマンドを足すときは1行足す
WRITE_TARGETS: dict[str, Callable[[tuple[str, ...]], list[str]]] = {
    **{name: _all_operands for name in (
        "tee", "mv", "rm", "rmdir", "unlink", "truncate", "touch", "chmod", "chown",
    )},
    **{name: _copy_like_targets for name in ("cp", "rsync", "install", "ln")},
    "dd": _dd_targets,
    "sed": _sed_targets,
    "perl": _perl_targets,
    "git": _git_targets,
    "find": _find_targets,
}


def _is_relative(word: str) -> bool:
    return bool(word) and not word.startswith(("/", "~", "$"))


def _find_start_paths(args: tuple[str, ...]) -> list[str]:
    """`find A B -name x …` の A B（探し始める場所）"""
    i = 0
    while i < len(args) and args[i] in ("-H", "-L", "-P"):
        i += 1
    paths = []
    for word in args[i:]:
        if word.startswith("-") or word in ("(", "!", ")", ","):
            break
        paths.append(word)
    return paths


# xargs が標準入力から読んだ語を後ろに足す位置の目印（実際の語には現れない）
_FED_ITEM = "\0fed"


def _write_targets(cmd: SimpleCommand) -> tuple[list[tuple[str, bool]], bool]:
    """([(この単純コマンドが書き込む先, 語の文字列が行き先そのものか)], 標準入力から来た語にも書き込むか)

    find -exec rm {} / find -delete は find の探し始める場所を、
    xargs rm は標準入力から来る語（＝どこから来たか分からない）を書き込み先とみなす。
    xargs の後ろの書き込み先は -I の置き換え文字列に標準入力の語がはめ込まれうるので、文字列が行き先そのものとは限らない
    """
    invs = invocations(cmd)
    targets: list[tuple[str, bool]] = []
    fed = False
    # find 自身が xargs から走る（xargs -I X find /tmp/X/… -delete）と、探し始める場所も
    # -exec の中の書き込み先（xargs -I X find . -exec rm /tmp/X/… \;）も文字列で決まらない
    not_from_xargs = bool(invs) and invs[0].via != "xargs"
    for inv in invs:
        extract = WRITE_TARGETS.get(inv.name)
        if extract is None:
            continue
        if inv.via == "xargs":
            found = extract(inv.args + (_FED_ITEM,))
            fed = fed or any(t == _FED_ITEM or "{}" in t for t in found)
            targets.extend((t, False) for t in found if t != _FED_ITEM)
            continue
        found = extract(inv.args)
        targets.extend((t, not_from_xargs) for t in found)
        if inv.via == "find" and any("{}" in t for t in found):
            targets.extend((t, not_from_xargs) for t in _find_start_paths(invs[0].args))
    if invs and invs[0].name == "find" and "-delete" in invs[0].args:
        targets.extend((t, not_from_xargs) for t in _find_start_paths(invs[0].args))
    return targets, fed


def _redirect_targets(cmd: SimpleCommand) -> list[Redirect]:
    """出力リダイレクトのうちファイルに書くもの（印 built を語ごとに判定へ渡すため Redirect のまま返す）"""
    targets = []
    for r in cmd.redirects:
        if r.op not in OUTPUT_REDIRECT_OPS or r.target.startswith("/dev/"):
            continue
        if r.op == ">&" and (r.target.isdigit() or r.target == "-"):
            continue  # 2>&1・>&2 は fd の複製で、ファイルへの書き込みではない
        targets.append(r)
    return targets


def _next_dir(cur: str | None, prev: str | None, inv: Invocation,
              project_dir: str | None, literal: bool = True) -> tuple[str | None, str | None]:
    """cd / pushd / popd の後の (今の場所, 直前の場所)。.claude の中にいるときだけ今の場所が文字列"""
    if inv.name == "popd":
        return prev, cur
    args = [a for a in inv.args if a == "-" or not a.startswith("-")]
    if args and args[0] == "-":
        return prev, cur
    dest = args[0] if args else ""  # 引数なしの cd はホームへ戻る
    if cur is not None and _is_relative(dest):
        dest = posixpath.join(cur, dest)
    if len(dest) > MAX_PATH_CHARS:
        return cur, prev  # bash でも cd が失敗する長さ。場所は変わらない（長い cd の連続で遅くならないように）
    dest = posixpath.normpath(dest) if dest else ""
    # 使い捨て置き場の .claude（/tmp/p/.claude/hooks）の中は「外」とみなす（9.5）
    inside = ".claude" in dest.split("/") and not is_disposable_path(dest, project_dir, literal)
    return (dest if inside else None), cur


def find_protected_write(cmds: list[SimpleCommand], project_dir: str | None) -> str | None:
    # 書き込み先を標準入力から受け取る（echo … | xargs rm）ときに使う。A1 と同じくコマンド全体の語で近似する。
    # 走査はコマンド全体で1回だけ（xargs が何度出ても O(n) に保つ）
    # 語は xargs に届くまでにパイプの途中（sed・tr・printf など）で加工されうるので、/tmp の下に見えても外さない（9.10）
    protected_word = next((w for cmd in cmds for w in cmd.words
                           if is_protected_path(w, project_dir, False)), None)
    # cd .claude/hooks && rm guard.py のように、中に入ってからの相対パスも保護対象とみなす。
    # 実行順に追い、`cd ..` などで出た後の書き込みは止めない
    cur: str | None = None
    prev: str | None = None
    for cmd in cmds:
        targets, fed = _write_targets(cmd)
        # WRITE_TARGETS の取り出し関数は語を加工した文字列（of= を外す・git -C とつなぐ）を返し、元の語に戻れない。
        # そのため書き込み先と cd は単純コマンドごとに見る（語のどれかに印があれば外さない。設計 12.11-1）
        literal = not cmd.built
        checks = ([(r.target, not r.built) for r in _redirect_targets(cmd)]
                  + [(t, source_literal and literal) for t, source_literal in targets])
        for target, target_literal in checks:
            if is_protected_path(target, project_dir, target_literal):
                return target
            if cur is not None and _is_relative(target):
                return f"{target}（cd {cur} の中）"
        if fed and protected_word is not None:
            return protected_word
        for inv in invocations(cmd):
            if inv.name in ("cd", "pushd", "popd"):
                cur, prev = _next_dir(cur, prev, inv, project_dir, literal)
    return None


def _git_push_force(args: tuple[str, ...]) -> str | None:
    for word in args:
        if word == "--force" or word.startswith("--force-with-lease"):
            return f"git push {word}"
        if "f" in bundle_letters(word):
            return f"git push {word}"
        if word.startswith("+"):
            return f"git push {word}"
    return None


def _git_reset(args: tuple[str, ...]) -> str | None:
    return "git reset --hard" if "--hard" in args else None


def _git_clean(args: tuple[str, ...]) -> str | None:
    # 強制と無視ファイルの削除が揃うと、.env など無視されている秘密ファイルまで消える
    force = any(a == "--force" or "f" in bundle_letters(a) for a in args)
    ignored = any("x" in bundle_letters(a) or "X" in bundle_letters(a) for a in args)
    if force and ignored:
        return "git clean " + " ".join(a for a in args if a.startswith("-"))
    return None


def _git_checkout_whole_tree(args: tuple[str, ...]) -> str | None:
    for word in operands(args):
        if word in WHOLE_TREE_PATHS:
            return f"git checkout {word}"
    return None


def _git_push_delete(args: tuple[str, ...]) -> str | None:
    """C1b。リモートのブランチ・タグを消す、またはローカルと丸ごと一致させる push"""
    for word in args:
        if word in GIT_PUSH_DELETE_OPTIONS:
            return f"git push {word}"
        # C1 の f と同じ読み方（束のどこにあっても当たる）
        if "d" in bundle_letters(word):
            return f"git push {word}"
        # コロンの左が空の refspec は削除の意味。`:` だけは matching push なので当てない
        if word.startswith(":") and len(word) > 1:
            return f"git push {word}"
    return None


def _forced_word(args: tuple[str, ...], long_options: frozenset[str], value_letters: str) -> str | None:
    """long_options と完全一致する語か、値を取る文字より前の束に f を含む語。最初のものを返す"""
    for word in args:
        if word in long_options or "f" in letters_before_value(word, value_letters):
            return word
    return None


def _git_checkout_force(args: tuple[str, ...]) -> str | None:
    """C2d。未コミットの変更を捨てて切り替える（git reset --hard 相当）"""
    word = _forced_word(args, GIT_CHECKOUT_FORCE_OPTIONS, GIT_CHECKOUT_VALUE_LETTERS)
    return f"git checkout {word}" if word else None


def _git_switch_force(args: tuple[str, ...]) -> str | None:
    """C2d。未コミットの変更を捨てて切り替える（git reset --hard 相当）"""
    word = _forced_word(args, GIT_SWITCH_FORCE_OPTIONS, GIT_SWITCH_VALUE_LETTERS)
    return f"git switch {word}" if word else None


# git サブコマンド → 規則の並び。先頭から試し、最初に該当した操作ラベルを返す
# （1規則＝1関数のまま並べることで、C1 などの既存規則の本体に手を入れずに規則を足せる）
GIT_IRREVERSIBLE: dict[str, tuple[Callable[[tuple[str, ...]], str | None], ...]] = {
    "push": (_git_push_force, _git_push_delete),                    # C1 → C1b
    "reset": (_git_reset,),                                          # C2
    "clean": (_git_clean,),                                          # C2b
    "checkout": (_git_checkout_whole_tree, _git_checkout_force),     # C2c → C2d
    "switch": (_git_switch_force,),                                  # C2d
}


def find_irreversible(cmds: list[SimpleCommand], project_dir: str | None) -> str | None:
    for cmd in cmds:
        for inv in invocations(cmd):
            if inv.name == "git":
                sub, rest = split_git(inv.args)
                for rule in GIT_IRREVERSIBLE.get(sub or "", ()):
                    label = rule(rest)
                    if label:
                        return label
            elif inv.name == "rm":
                # -f の有無は問わない。破壊の本体は再帰のため
                recursive = [a for a in inv.args
                             if a == "--recursive" or any(ch in bundle_letters(a) for ch in "rR")]
                if not recursive:
                    continue
                for target in operands(inv.args):
                    if is_broad_target(target, project_dir):
                        return f"rm {recursive[0]} {target}"
    return None


# ---------------------------------------------------------------------------
# 公開面
# ---------------------------------------------------------------------------

def _sanitize(text: str) -> str:
    cleaned = "".join(" " if (ord(ch) < 32 or ord(ch) == 127) else ch for ch in text)
    if len(cleaned) > MAX_TARGET_CHARS:
        cleaned = cleaned[:MAX_TARGET_CHARS] + "…"
    return cleaned


def format_reason(category: str, target: str, advice: str) -> str:
    return f"guard: {category}のため止めました: {_sanitize(target)}\n次にやること: {advice}"


def check_command(command: str, project_dir: str | None = None) -> str | None:
    """止めるなら理由（AI に返す文）を、通すなら None を返す。純粋関数。

    例外は外に投げる（main が fail-open にする。テストでバグが見えるように握りつぶさない）。
    """
    cmds = collect(command)
    target = find_secret_read(cmds, command, project_dir)  # 【LES】
    if target:
        return format_reason(CATEGORY_SECRET, target, ADVICE_SECRET)
    target = find_protected_write(cmds, project_dir)
    if target:
        return format_reason(CATEGORY_PROTECTED, target, ADVICE_PROTECTED)
    target = find_irreversible(cmds, project_dir)
    if target:
        return format_reason(CATEGORY_IRREVERSIBLE, target, ADVICE_IRREVERSIBLE)
    return None


def main(stdin=None, stderr=None, environ=None) -> int:
    """フックの入口。止めるなら理由を stderr に書いて 2、それ以外は必ず 0"""
    # 既定値は定義時に束縛しない（テストで差し替えるため）
    stdin = sys.stdin if stdin is None else stdin
    stderr = sys.stderr if stderr is None else stderr
    environ = os.environ if environ is None else environ
    try:
        data = json.loads(stdin.read())
        if not isinstance(data, dict):
            return 0
        # matcher が Bash なので欠落は想定外。止める側に倒しても誤検知の害はない
        if data.get("tool_name", "Bash") != "Bash":
            return 0
        tool_input = data.get("tool_input")
        if not isinstance(tool_input, dict):
            return 0
        command = tool_input.get("command")
        if not isinstance(command, str):
            return 0
        reason = check_command(command, environ.get("CLAUDE_PROJECT_DIR") or None)
    except Exception:
        return 0  # guard の故障で Bash 全体を止めない
    if reason is None:
        return 0
    try:
        stderr.write(reason + "\n")
        stderr.flush()
    except Exception:
        pass
    return 2  # 判定は済んでいる。理由が届かなくても通すと秘密が出る側に倒れる


if __name__ == "__main__":
    try:
        # Claude Code は UTF-8 の JSON を渡す。ロケールに左右されないように固定する
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        exit_code = main()
    except BaseException:
        exit_code = 0
    sys.exit(exit_code if exit_code in (0, 2) else 0)
