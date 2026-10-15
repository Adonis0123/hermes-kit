# Figma Copy Proofread

Keep a Figma design frame's copy in line with the live page's copy, so the copy team stops re-commenting the same fixes on every new design version.

## Language

**Live Copy (线上文案)**:
The text a user sees on the live (or test) page at the given URL. It is the source of truth.
_Avoid_: 线上词条, source copy

**Copy Catalog (文案目录)**:
The full set of Live Copy the app ships, read from the source catalog of the branch deployed at the live URL's domain. It holds every string a page can show (dialogs and tooltips included) but not which slot shows it, and never holds user data.
_Avoid_: 词库, 翻译文件, i18n 文件

**Design Copy (设计稿文案)**:
The text in one Figma frame's visible text layers.
_Avoid_: 设计稿词条, figma text

**Copy Pair (词条对)**:
One Design Copy and one Live Copy judged to fill the same slot on the page (the same button, title, or label), even when the wording is fully rewritten.
_Avoid_: match, 对齐项

**Mismatch (差异)**:
A Copy Pair whose two texts differ. Only Mismatches get a Proofread Comment.

**Unmatched Copy (未匹配文案)**:
Design Copy with no Copy Pair on the live page. It is reported, never commented.

**Mismatch List (差异清单)**:
The numbered list of Mismatches the bot sends back in Feishu before writing anything to Figma.

**Proofread Comment (校对评论)**:
A Figma comment pinned to a Mismatch's text layer that says what the Live Copy is.

## Relationships

- A proofread run compares exactly one Figma frame with one live URL.
- **Live Copy** comes from the **Copy Catalog** when the site has one; the live page is opened only to settle Copy Pairs the catalog cannot place.
- Design Copy found as-is in the **Copy Catalog** is taken as matching; only the rest can become a **Mismatch** or **Unmatched Copy**.
- A **Copy Pair** holds exactly one **Design Copy** and one **Live Copy**.
- Every **Mismatch** is a **Copy Pair**; a **Proofread Comment** is written only for a **Mismatch** the user confirmed in the **Mismatch List**.

## Example dialogue

> **Copy team:** "The design says A for copy1 and the live page says B. Does that count?"
> **Dev:** "If both sit in the same slot, it is a **Copy Pair** with a **Mismatch**. After you confirm it in the **Mismatch List**, it gets a **Proofread Comment** saying B."

## Flagged ambiguities

- "词条" was used for both a copy key (copy1) and its text. It is resolved to **Copy Pair**: the slot, identified by position and context. The **Copy Catalog** keys strings by their own English text, so a catalog entry is a Live Copy, not a slot.
