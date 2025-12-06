# Translation Rules

## General Principles (Ranked by Priority)

1. **Accuracy** - Preserve original meaning completely
2. **Technical Integrity** - Keep all tags, variables, formatting intact
3. **Naturalness** - Sound natural and fluent in Russian
4. **Cultural Authenticity** - Maintain Wuxia and ancient China atmosphere
5. **Consistency** - Use same terms throughout (consult terminology tables)
6. **Player Experience** - Readable, immersive, appropriate for gaming context

## Critical Technical Rules

### Tags and Variables (ABSOLUTE REQUIREMENTS)

**NEVER translate or modify these:**
- `{0}`, `{1}`, `{2}`, `{name}`, `{count}`, `{value}` - Variable placeholders
- `{PlayerName}`, `{QuestName}`, `{ItemName}` - Named variables
- `<color>`, `</color>`, `<b>`, `</b>` - HTML-like tags
- `<Something|123|#C|456>` - Game-specific tags (keep EXACTLY as-is)
- `#Y`, `#E`, `#C`, `#R`, `#G`, `#B`, `#W` - Color codes
- `\n` - Newline (preserve count and position)
- `\r`, `\t` - Carriage return, tab

**Examples:**

❌ WRONG:
```
EN: "Increases <Max Attack|780|#C|151> by {0}%"
RU: "Увеличивает <Макс. атаку|780|#C|151> на {0}%"
```

✅ CORRECT:
```
EN: "Increases <Max Attack|780|#C|151> by {0}%"
RU: "Увеличивает <Max Attack|780|#C|151> на {0}%"
```

❌ WRONG:
```
EN: "Line 1\nLine 2"
RU: "Строка 1 Строка 2"
```

✅ CORRECT:
```
EN: "Line 1\nLine 2"
RU: "Строка 1\nСтрока 2"
```

### Special Sequences to Preserve

**Bracketed placeholders** - Usually translate, but verify in context:
- `[Item Name]` → `[Название предмета]` ✅
- `[Recruit Fellowship]` → `[Рекрутировать спутников]` ✅
- But if contains code/numbers: `[Lv.50]` → `[Lv.50]` (keep as-is)

## Translation by Content Type

### 1. UI/System Messages

**Style**: Concise, imperative, clear
**Length**: Shorter is better (UI space limited)

**Examples:**
- "Quest completed" → "Задание выполнено" (not "Вы успешно завершили квест")
- "Item obtained" → "Предмет получен"
- "Level up!" → "Новый уровень!"
- "Save progress?" → "Сохранить прогресс?"
- "Loading..." → "Загрузка..."
- "Press any key to continue" → "Нажмите любую клавишу"
- "Confirm action" → "Подтвердить"
- "Cancel" → "Отмена"

### 2. Quest Titles & Objectives

**Style**: Clear, action-oriented, atmospheric
**Length**: Keep concise but meaningful

**Examples:**
- "The Missing Scholar" → "Пропавший учёный"
- "Defend the Village" → "Защита деревни" (not "Защитите деревню" - noun form for title)
- "Journey to Mount Tai" → "Путешествие к горе Тай"
- "Collect 5 herbs" → "Соберите 5 трав" (verb form for objective)
- "Defeat the bandit leader" → "Победите главаря бандитов"

### 3. Dialogue

**Key Principles:**
- Use appropriate formality level (see below)
- Natural speech patterns
- Maintain character personality
- Period-appropriate language

**Formality Levels:**

**Formal (to elders, masters, nobles):**
- Use "вы", "Вы" (capitalized for high respect)
- Respectful forms: "Учитель", "Мастер", "Господин"
- Longer, more elaborate sentences

```
EN: "Master, I seek your guidance"
RU: "Учитель, я ищу Вашего наставления"
```

**Semi-formal (peers, colleagues):**
- Use "вы" (lowercase)
- Neutral vocabulary

```
EN: "We should work together"
RU: "Нам стоит работать вместе"
```

**Informal (to juniors, friends, subordinates):**
- Use "ты"
- Casual but not modern slang

```
EN: "Follow me, young one"
RU: "Следуй за мной, юнец"
```

**Imperial/Court dialogue:**
- Elevated, archaic style
- Court vocabulary: "государь", "Ваше Величество", "дворец", "повеление"

```
EN: "Your Majesty, the rebels approach"
RU: "Ваше Величество, мятежники приближаются"
```

### 4. Combat Skills & Abilities

**Style**: Dynamic, impactful, concise
**Format**: Usually short phrases (2-4 words)

**Examples:**
- "Thundering Strike" → "Громовой удар"
- "Dragon's Fury" → "Ярость дракона"
- "Swift Blade" → "Быстрый клинок"
- "Internal Energy Burst" → "Взрыв внутренней силы"
- "Flying Sword Technique" → "Техника летающего меча"
- "Meditation Recovery" → "Восстановление медитацией"

**Skill Descriptions:**
- Active voice, present tense
- Lead with effect, then mechanism

```
EN: "Strikes the enemy with lightning-fast speed, dealing {0} damage"
RU: "Наносит удар молниеносной скорости, причиняя {0} урона"
```

### 5. Item Names & Descriptions

**Legendary/Epic Items:**
- Poetic, evocative
- Preserve Chinese naming conventions when appropriate

```
EN: "Jade Dragon Blade - A sword forged from celestial jade"
RU: "Клинок Нефритового Дракона — меч, выкованный из небесного нефрита"
```

**Common Items:**
- Simple, functional

```
EN: "Healing Herb - Restores 50 HP"
RU: "Целебная трава — восстанавливает 50 HP"
```

**Currency/Resources:**
- Keep common gaming terms

```
EN: "Gold" → "Золото"
EN: "Silver" → "Серебро"
EN: "XP" → "Опыт" or "XP" (context-dependent)
```

### 6. Lore & Historical Text

**Style**: Elevated, respectful, slightly archaic
**Preserve**: Cultural concepts, proper nouns

```
EN: "In the age of Ten Kingdoms, the Jianghu was a place of honor and betrayal"
RU: "В эпоху Десяти Царств Цзянху был местом чести и предательства"
```

**Use archaic markers:**
- "сей" (this), "оный" (that) - sparingly
- Old verb forms - only if natural
- Keep readable - don't overdo archaism

### 7. Tutorial & Help Text

**Style**: Clear, instructive, patient
**Avoid**: Overly formal or condescending tone

```
EN: "Use WASD to move your character. Press Space to jump."
RU: "Используйте WASD для перемещения персонажа. Нажмите Пробел для прыжка."
```

## Names & Proper Nouns

### Character Names (Chinese)

**Transliteration System:**
- Use established Russian transliteration of Chinese
- Maintain original order (surname + given name)

**Examples:**
- 李明 (Li Ming) → Ли Мин
- 王小龙 (Wang Xiaolong) → Ван Сяолун
- 张三 (Zhang San) → Чжан Сань
- 欧阳 (Ouyang) → Оуян

**Single-character surnames:**
- 李 → Ли, 王 → Ван, 张 → Чжан, 刘 → Лю
- 陈 → Чэнь, 杨 → Ян, 黄 → Хуан
- 周 → Чжоу, 吴 → У, 徐 → Сюй

### Titles & Honorifics

**Keep original + transliterate for important titles:**
- 师父 → Шифу (Учитель) - first mention, then just Шифу
- 大侠 → Дася (Великий воин)
- 掌门 → Чжанмэнь (Глава школы)

**Translate generic titles:**
- Master → Мастер
- Lord → Господин
- General → Генерал
- Emperor → Император

### Place Names

**Major locations:** Transliterate + explain if first mention
- 燕云 (Yan Yun) → Янь Юнь
- 少林寺 (Shaolin Temple) → Храм Шаолинь

**Generic places:** Translate
- "The Eastern Village" → "Восточная деревня"
- "Black Mountain" → "Чёрная гора"

### Technique/School Names

**Legendary techniques:** Transliterate + translate meaning in parentheses if first use
- 降龙十八掌 → Восемнадцать ладоней покорения дракона
- 太极剑 → Меч Тайцзи
- 九阳真经 → Канон девяти солнц

**Common techniques:** Translate
- "Sword Technique" → "Техника меча"
- "Fist Method" → "Кулачная техника"

## Length Control

Russian is typically **15-30% longer** than English.

### When Translation is TOO LONG (2x+ of English):

**UI/System text:**
1. Use shorter synonyms
2. Remove unnecessary particles ("же", "ведь", "то")
3. Use abbreviated forms common in gaming

```
EN: "Successfully completed" (20 chars)
❌ BAD: "Успешно завершено выполнение" (28 chars, 40% longer - OK)
❌ WORSE: "Вы успешно завершили выполнение задания" (39 chars, 95% longer - TOO LONG)
✅ GOOD: "Выполнено" (10 chars)
```

**Dialogue/Lore:**
- Preserve full meaning
- Length is acceptable if natural
- Only condense if translation sounds verbose in Russian

```
EN: "The ancient masters spoke of a legendary warrior" (50 chars)
RU: "Древние мастера говорили о легендарном воине" (45 chars)
✅ Natural length, good translation
```

### Strategies for Conciseness

1. **Nominative forms in titles:**
   - "Защита деревни" not "Защитите деревню"

2. **Drop redundant pronouns:**
   - "Выполнено" not "Вы выполнили"

3. **Use common gaming abbreviations:**
   - HP, MP, XP (when appropriate)
   - DMG → урон
   - DEF → защита

4. **Participle constructions:**
   - "полученный" instead of "который получен"

## Consistency & Terminology

### Critical Terms (ALWAYS translate the same way)

**Core Wuxia Concepts:**
- Qi → Ци (never "энергия" alone)
- Jianghu → Цзянху / мир боевых искусств
- Internal Energy → Внутренняя сила / Нэйгун (skill names)
- Lightness Skill → Искусство лёгкости / Цингун
- Martial Arts → Боевые искусства / Ушу

**Game Systems:**
- Quest → Задание (never "квест" unless UI space critical)
- Level → Уровень
- Skill → Навык (passive) / Умение (active ability)
- Guild → Гильдия
- Party → Группа
- Inventory → Инвентарь

**Combat:**
- Attack → Атака
- Defense → Защита
- Damage → Урон
- HP (Health) → HP / Здоровье
- MP (Mana) → MP / Внутренняя энергия

### Create Terminology Memory

As you translate, remember:
1. First occurrence of special term - be precise
2. Subsequent uses - be consistent
3. Check context for variations

## Common Pitfalls & How to Avoid

### ❌ Don't Do This:

1. **Translating game tags:**
   - `<Player|123>` → `<Игрок|123>` ❌

2. **Changing variable format:**
   - `{0}` → `{ноль}` ❌

3. **Modernizing historical dialogue:**
   - "Yo, master, what's up?" → "Йоу, мастер, как дела?" ❌

4. **Losing newlines:**
   - Forgetting to count and place `\n` correctly ❌

5. **Over-explaining:**
   - "Qi (китайская жизненная энергия, циркулирующая...)" ❌
   - Just "Ци" ✅ (context will explain)

6. **Breaking game code:**
   - Spaces in variables: `{ 0 }` instead of `{0}` ❌

### ✅ Do This:

1. **Preserve all technical elements**
2. **Use established terminology**
3. **Read Chinese context when available** (helps with ambiguity)
4. **Keep cultural authenticity**
5. **Sound natural in Russian**
6. **Maintain appropriate formality**

## Quality Check (Self-Verification)

Before finalizing each translation, mentally check:

1. ✓ All `{variables}` and `<tags>` intact?
2. ✓ Same number of `\n` as original?
3. ✓ Cultural terms consistent with glossary?
4. ✓ Appropriate formality level for context?
5. ✓ Natural Russian sentence flow?
6. ✓ Meaning preserved completely?
7. ✓ Length reasonable for context (UI vs dialogue)?
8. ✓ No modern slang in historical context?

## Few-Shot Examples

### Example 1: UI Message

```
EN: "Quest failed. Return to quest giver to retry."
ZH: "任务失败。返回任务发布者重试。"

Analysis: UI system message, needs to be concise

RU: "Задание провалено. Вернитесь к заказчику для повтора."
```

### Example 2: NPC Dialogue (Formal)

```
EN: "Young warrior, your skills are impressive. I shall teach you a secret technique."
ZH: "少侠，你的技艺令人赞叹。我将传授你秘技。"

Analysis: Elder to younger, formal, martial arts context

RU: "Молодой воин, твоё мастерство впечатляет. Я обучу тебя секретной технике."
```

### Example 3: Skill Description

```
EN: "Dragon's Roar: Unleashes a powerful shout that damages all enemies within 10m and reduces their Attack by {0}% for 5 seconds."
ZH: "龙吟：释放强大的吼叫，对10米内所有敌人造成伤害，并降低{0}%攻击力，持续5秒。"

Analysis: Skill, needs {0} preserved, dynamic description

RU: "Рык дракона: Испускает мощный крик, наносящий урон всем врагам в радиусе 10 м и снижающий их атаку на {0}% на 5 сек."
```

### Example 4: Item Description

```
EN: "Jade Phoenix Hairpin - An exquisite ornament worn by martial arts masters. Increases Spirit by 50."
ZH: "玉凤钗 - 武林高手佩戴的精美饰品。提升精神50点。"

Analysis: Legendary item, poetic style, game stats

RU: "Шпилька Нефритового Феникса — изысканное украшение, которое носят мастера боевых искусств. Увеличивает Дух на 50."
```

### Example 5: Quest Text with Tags

```
EN: "Travel to <Ancient Temple|5421|#C|892> and speak with <Elder Wu|6234|#Y|145>.\nReward: {0} Gold, {1} XP"
ZH: "前往<古寺|5421|#C|892>与<吴长老|6234|#Y|145>交谈。\n奖励：{0}金币，{1}经验"

Analysis: Quest objective with game tags, must preserve exactly, has \n

RU: "Отправляйтесь в <Ancient Temple|5421|#C|892> и поговорите с <Elder Wu|6234|#Y|145>.\nНаграда: {0} золота, {1} опыта"
```

## Prohibited Actions

**NEVER:**
- Change, translate, or modify `{variables}` or `<game|tags>`
- Add content not in original (no explanatory notes in translation)
- Remove content from original
- Change meaning for "humor" or "localization creativity"
- Use modern slang in historical/traditional context
- Translate proper names without considering Chinese transcription rules
- Cut important meaning for brevity (only condense UI when necessary)
- Change formality level inappropriately
- Ignore Chinese context when provided (it helps accuracy)

## Special Cases

### Ambiguous English

When English is ambiguous, **use Chinese context (ZH) to clarify:**

```
EN: "Light" (could be: light/lightweight, or light/illumination, or light/pale color)
ZH: "轻" → lightweight/light (not heavy)
RU: "Лёгкий"

EN: "Light"
ZH: "光" → light/illumination
RU: "Свет"
```

### Repeated Context

When you see previous translations (REFERENCE section):
- **Maintain consistency** with established term choices
- **Match tone and style**
- Use as guide for character relationships/formality

### Numbers and Measurements

- Keep metric system as-is: "10m" → "10 м"
- Percentages: "{0}%" → "{0}%"
- Time: "5 seconds" → "5 сек." or "5 секунд" (depends on space)

---

**Remember**: You are creating an immersive experience for Russian players. Balance accuracy, naturalness, and cultural authenticity while maintaining technical integrity. When in doubt, prioritize meaning preservation and technical correctness over stylistic flourishes.
