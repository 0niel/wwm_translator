# Translation Examples - Best Practices

This file contains curated examples of high-quality translations for reference.

## UI & System Messages

### Concise & Clear

```
EN: "Quest completed successfully"
ZH: "任务成功完成"
RU: "Задание выполнено"
✓ Concise, removed "successfully" (redundant in RU gaming context)

EN: "Item added to inventory"
ZH: "物品已添加到背包"
RU: "Предмет добавлен в инвентарь"
✓ Clear, direct

EN: "Are you sure you want to quit?"
ZH: "确定要退出吗？"
RU: "Вы уверены, что хотите выйти?"
✓ Natural question form

EN: "Loading world data..."
ZH: "加载世界数据中..."
RU: "Загрузка мира..."
✓ Short for loading screen

EN: "Press {0} to interact"
ZH: "按{0}交互"
RU: "Нажмите {0} для взаимодействия"
✓ Variable preserved, clear instruction
```

### Status Messages

```
EN: "Level up! You are now level {0}"
ZH: "升级了！你现在是{0}级"
RU: "Новый уровень! Теперь вы {0} уровня"
✓ Exciting tone, grammatically correct

EN: "Not enough gold"
ZH: "金币不足"
RU: "Недостаточно золота"
✓ Concise warning

EN: "Quest progress: {0}/{1}"
ZH: "任务进度：{0}/{1}"
RU: "Прогресс: {0}/{1}"
✓ Very short for UI, both variables intact
```

## Combat & Skills

### Skill Names (Dynamic & Impactful)

```
EN: "Thundering Strike"
ZH: "雷霆打击"
RU: "Громовой удар"
✓ Dynamic, noun + adjective

EN: "Dragon's Descent"
ZH: "神龙降世"
RU: "Нисхождение дракона"
✓ Poetic, genitive case

EN: "Blade Flurry"
ZH: "剑刃风暴"
RU: "Вихрь клинков"
✓ Evocative, plural

EN: "Internal Energy Burst"
ZH: "内力爆发"
RU: "Взрыв внутренней силы"
✓ Wuxia terminology preserved

EN: "Swift Wind Step"
ZH: "疾风步"
RU: "Шаг быстрого ветра"
✓ Technique name style
```

### Skill Descriptions

```
EN: "Strikes the target 3 times, dealing {0} damage each hit. Cooldown: {1} seconds."
ZH: "攻击目标3次，每次造成{0}伤害。冷却时间：{1}秒。"
RU: "Наносит по цели 3 удара, каждый причиняет {0} урона. Восстановление: {1} сек."
✓ Both variables intact, "cooldown" → "восстановление" (common RU gaming term)

EN: "Channels internal energy to <Restore HP|234|#G|500> by {0} over 5 seconds"
ZH: "运气恢复<生命值|234|#G|500>{0}，持续5秒"
RU: "Направляет внутреннюю энергию на <Restore HP|234|#G|500> {0} за 5 сек."
✓ Tag unchanged, Wuxia terminology, time abbreviated

EN: "Increases <Attack Power|101|#R|200> by {0}% and grants immunity to crowd control"
ZH: "提升<攻击力|101|#R|200>{0}%并免疫控制效果"
RU: "Увеличивает <Attack Power|101|#R|200> на {0}% и даёт невосприимчивость к контролю"
✓ Tag intact, gaming terminology ("контроль" for CC)
```

### Combat Log Messages

```
EN: "Critical hit! Dealt {0} damage"
ZH: "暴击！造成{0}伤害"
RU: "Критический удар! Нанесено {0} урона"
✓ Exciting, variable preserved

EN: "Blocked {0} damage"
ZH: "格挡了{0}伤害"
RU: "Заблокировано {0} урона"
✓ Passive voice (RU gaming standard)

EN: "Dodged attack"
ZH: "闪避攻击"
RU: "Атака уклонена"
✓ Concise
```

## Dialogue

### Formal (Student to Master)

```
EN: "Master, I have completed the training you assigned"
ZH: "师父，我完成了您布置的训练"
RU: "Учитель, я завершил тренировку, которую Вы мне дали"
✓ Formal "Вы" (capitalized), respectful tone

EN: "Please teach me your legendary sword technique"
ZH: "请传授我您的传奇剑法"
RU: "Прошу обучить меня Вашей легендарной технике меча"
✓ Very formal request, "Вашей" capitalized

EN: "I seek to understand the way of the warrior"
ZH: "我想要理解武者之道"
RU: "Я стремлюсь постичь путь воина"
✓ Elevated vocabulary "постичь" (comprehend deeply)
```

### Informal (Master to Student)

```
EN: "You have much to learn, young one"
ZH: "你还有很多要学的，年轻人"
RU: "Тебе многому ещё предстоит научиться, юнец"
✓ Informal "ты", slightly archaic "юнец" for period feel

EN: "Show me what you've learned"
ZH: "展示给我你学到的东西"
RU: "Покажи, чему ты научился"
✓ Informal, direct

EN: "Not bad. Your technique is improving"
ZH: "不错。你的技术在进步"
RU: "Неплохо. Твоя техника улучшается"
✓ Natural speech, informal
```

### Peers (Semi-formal)

```
EN: "We should team up for this quest"
ZH: "我们应该组队完成这个任务"
RU: "Нам стоит объединиться для этого задания"
✓ Neutral, no "ты/вы", cooperative tone

EN: "Have you heard the rumors about the northern bandits?"
ZH: "你听说过北方盗匪的传闻吗？"
RU: "Ты слышал слухи о северных бандитах?"
✓ Informal among peers

EN: "Let's meet at the tavern tonight"
ZH: "今晚在客栈见面吧"
RU: "Встретимся в таверне вечером"
✓ Natural conversation
```

### Imperial/Court Dialogue

```
EN: "Your Majesty, the enemy forces approach the capital"
ZH: "陛下，敌军正在逼近都城"
RU: "Ваше Величество, вражеские силы приближаются к столице"
✓ Highest respect form, formal vocabulary

EN: "The Emperor commands your presence in the throne room"
ZH: "皇帝召见你到大殿"
RU: "Император повелевает вам явиться в тронный зал"
✓ Imperial tone, formal "повелевает" (commands)

EN: "By imperial decree, all citizens must..."
ZH: "根据皇帝诏书，所有公民必须..."
RU: "Согласно императорскому указу, все граждане должны..."
✓ Official proclamation style
```

## Quest Text

### Quest Titles

```
EN: "The Missing Scholar"
ZH: "失踪的学者"
RU: "Пропавший учёный"
✓ Noun form, atmospheric

EN: "Defend the Village"
ZH: "守卫村庄"
RU: "Защита деревни"
✓ Noun form for title (not verb)

EN: "Journey to Mount Tai"
ZH: "前往泰山"
RU: "Путешествие к горе Тай"
✓ Transcription "Тай", descriptive

EN: "The Sect Leader's Trial"
ZH: "掌门的考验"
RU: "Испытание главы школы"
✓ Genitive case, Wuxia terminology
```

### Quest Objectives

```
EN: "Collect 10 medicinal herbs from the forest"
ZH: "从森林收集10株药草"
RU: "Соберите 10 целебных трав в лесу"
✓ Verb form for objective, clear

EN: "Defeat the bandit leader and his guards"
ZH: "击败盗匪头目和他的守卫"
RU: "Победите главаря бандитов и его охрану"
✓ Action-oriented

EN: "Speak with <Elder Chen|5678|#Y|234> at the temple"
ZH: "在寺庙与<陈长老|5678|#Y|234>交谈"
RU: "Поговорите с <Elder Chen|5678|#Y|234> в храме"
✓ Tag unchanged, natural location
```

### Quest Descriptions

```
EN: "A mysterious illness has struck the village. The local healer believes that rare herbs from the mountains can cure it. Will you help?"
ZH: "一种神秘疾病袭击了村庄。当地医师相信山上的稀有草药可以治愈。你愿意帮忙吗？"
RU: "Таинственная болезнь поразила деревню. Местный лекарь полагает, что редкие травы с гор могут излечить её. Поможете?"
✓ Narrative flow, natural Russian, question at end

EN: "The ancient temple holds secrets of forgotten martial arts. Explore its depths and discover the truth.\n\nReward:\n- {0} Gold\n- {1} XP\n- Rare Technique Scroll"
ZH: "古寺蕴藏着失传武学的秘密。探索其深处，发现真相。\n\n奖励：\n- {0}金币\n- {1}经验\n- 稀有功法卷轴"
RU: "Древний храм хранит секреты забытых боевых искусств. Исследуйте его глубины и откройте истину.\n\nНаграда:\n- {0} золота\n- {1} опыта\n- Свиток редкой техники"
✓ All \n preserved, both variables intact, atmospheric description
```

## Items

### Legendary Weapons

```
EN: "Jade Dragon Blade - A legendary sword forged from celestial jade, said to contain the spirit of an ancient dragon. Increases Attack by 500 and grants the skill <Dragon's Fury|8901|#R|345>"
ZH: "玉龙刀 - 传说中用天界玉石锻造的宝剑，据说蕴含着古龙之魂。增加500攻击力并赋予技能<龙之狂怒|8901|#R|345>"
RU: "Клинок Нефритового Дракона — легендарный меч, выкованный из небесного нефрита, который, как говорят, содержит дух древнего дракона. Увеличивает атаку на 500 и даёт умение <Dragon's Fury|8901|#R|345>"
✓ Poetic, tag intact, evocative lore

EN: "Phoenix Feather Fan - Wielded by martial arts masters, this elegant weapon channels internal energy with deadly precision"
ZH: "凤羽扇 - 武林高手使用的优雅武器，以致命的精准度引导内力"
RU: "Веер Пера Феникса — изящное оружие мастеров боевых искусств, направляющее внутреннюю энергию с смертоносной точностью"
✓ Wuxia terminology, flowing description
```

### Common Items

```
EN: "Health Potion - Restores {0} HP"
ZH: "生命药水 - 恢复{0}生命值"
RU: "Зелье здоровья — восстанавливает {0} HP"
✓ Simple, functional, variable intact

EN: "Iron Sword - A basic weapon. Attack +20"
ZH: "铁剑 - 基础武器。攻击+20"
RU: "Железный меч — обычное оружие. Атака +20"
✓ Concise common item

EN: "Steamed Bun - Tasty snack. Recovers 50 HP over 10 seconds"
ZH: "馒头 - 美味小吃。10秒内恢复50生命值"
RU: "Паровая булочка — вкусная закуска. Восстанавливает 50 HP за 10 сек."
✓ Cultural food item, mechanics clear
```

### Materials & Resources

```
EN: "Spirit Stone - Used for enhancing equipment. Rare material."
ZH: "灵石 - 用于强化装备。稀有材料。"
RU: "Камень духа — используется для усиления снаряжения. Редкий материал."
✓ Clear purpose, concise

EN: "Ancient Scroll Fragment - Combine 5 fragments to unlock a secret technique"
ZH: "古卷碎片 - 集齐5个碎片解锁秘技"
RU: "Фрагмент древнего свитка — соберите 5 фрагментов, чтобы открыть секретную технику"
✓ Collection mechanic clear
```

## Lore & History

### Historical Text

```
EN: "During the Five Dynasties period, the land was divided among warring kingdoms. In this chaos, the Jianghu emerged as a world unto itself, where martial artists followed their own code of honor."
ZH: "五代时期，大地被交战的王国分割。在这种混乱中，江湖作为一个独立的世界出现，武者遵循自己的荣誉准则。"
RU: "В эпоху Пяти Династий земли были разделены между враждующими царствами. В этом хаосе Цзянху возник как отдельный мир, где мастера боевых искусств следовали собственному кодексу чести."
✓ Elevated style, Chinese terms preserved, historical tone

EN: "The ancient masters spoke of three treasures: Jing (essence), Qi (energy), and Shen (spirit). To cultivate all three was to achieve harmony with the Dao."
ZH: "古代大师谈到三宝：精、气、神。修炼这三者即可与道和谐。"
RU: "Древние мастера говорили о трёх сокровищах: Цзин (сущность), Ци (энергия) и Шэнь (дух). Развивать все три означало достичь гармонии с Дао."
✓ Philosophical concepts with transcription + translation
```

### NPC Background

```
EN: "Master Liu studied under the legendary Sect Leader of Mount Hua. After years of training, he returned to his hometown to establish his own school."
ZH: "刘师傅曾在传奇的华山掌门门下学习。经过多年训练，他回到家乡建立了自己的门派。"
RU: "Мастер Лю обучался у легендарного главы школы горы Хуашань. После многих лет тренировок он вернулся в родной город, чтобы основать собственную школу."
✓ Chinese name transcribed, place name transcribed, narrative flow
```

## Technical Patterns

### Tags with Complex Nesting

```
EN: "Consumes <Internal Energy|567|#B|890> to increase <Attack Speed|123|#Y|456> by {0}% and <Critical Chance|234|#R|567> by {1}%"
ZH: "消耗<内力|567|#B|890>以提升<攻击速度|123|#Y|456>{0}%和<暴击几率|234|#R|567>{1}%"
RU: "Расходует <Internal Energy|567|#B|890> для увеличения <Attack Speed|123|#Y|456> на {0}% и <Critical Chance|234|#R|567> на {1}%"
✓ All three tags unchanged, both variables intact
```

### Multiple Newlines

```
EN: "Quest: The Lost Artifact\n\nDescription:\nFind the ancient artifact hidden in the ruins.\n\nReward: {0} Gold"
ZH: "任务：遗失的神器\n\n描述：\n在废墟中找到隐藏的古老神器。\n\n奖励：{0}金币"
RU: "Задание: Утерянный артефакт\n\nОписание:\nНайдите древний артефакт, спрятанный в руинах.\n\nНаграда: {0} золота"
✓ All \n preserved exactly (double \n for blank line)
```

### Conditional Text

```
EN: "{0} has joined your party"
ZH: "{0}加入了你的队伍"
RU: "{0} присоединился к вашей группе"
✓ Variable at start, grammatically flexible in RU

EN: "Unlock at Level {0}"
ZH: "{0}级解锁"
RU: "Открывается на {0} уровне"
✓ Grammatical restructure while preserving variable
```

## Common Mistakes & Corrections

### ❌ Mistake 1: Translating Game Tags

```
WRONG:
EN: "Increases <Max HP|101|#G|500> by 100"
RU: "Увеличивает <Макс. HP|101|#G|500> на 100"

CORRECT:
RU: "Увеличивает <Max HP|101|#G|500> на 100"
→ Tag must stay in English, untouched
```

### ❌ Mistake 2: Losing Newlines

```
WRONG:
EN: "Line 1\nLine 2\nLine 3"
RU: "Строка 1 Строка 2 Строка 3"

CORRECT:
RU: "Строка 1\nСтрока 2\nСтрока 3"
→ Must preserve \n count and position
```

### ❌ Mistake 3: Wrong Formality

```
WRONG:
EN: "Master, please teach me" (student to master)
RU: "Мастер, пожалуйста научи меня" (informal "научи")

CORRECT:
RU: "Мастер, прошу обучить меня" (formal request)
→ Student must use formal to master
```

### ❌ Mistake 4: Over-explaining

```
WRONG:
EN: "The Qi flows through your meridians"
RU: "Ци (жизненная энергия в китайской философии) течёт по вашим меридианам (энергетическим каналам)"

CORRECT:
RU: "Ци течёт по вашим меридианам"
→ Context explains, no need for parenthetical notes
```

### ❌ Mistake 5: Modern Slang in Historical Context

```
WRONG:
EN: "This technique is amazing!"
ZH: "这个技巧太棒了！"
RU: "Эта техника крутая!" (too casual)

CORRECT:
RU: "Эта техника поразительна!" or "Эта техника великолепна!"
→ Period-appropriate vocabulary
```

## Summary Checklist

For every translation, verify:

- [ ] All {variables} unchanged
- [ ] All <tags|with|content> unchanged  
- [ ] Color codes (#Y, #C, etc.) unchanged
- [ ] \n count matches original
- [ ] Formality appropriate for context
- [ ] Wuxia terminology consistent
- [ ] Natural Russian sentence flow
- [ ] Length appropriate for content type
- [ ] Meaning completely preserved
- [ ] No modern slang in historical context

---

Use these examples as reference for quality and consistency. When in doubt, refer to the detailed rules in `translation_rules.md`.

