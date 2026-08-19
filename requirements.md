1. ## 产品定位
    

- **平台**：Discord
    
- **社区类型**：
    
    - AI roleplay app创作者社区
        
    - 女性用户为主
        
    - 同人 / OC / 原创内容爱好者为主
        
    - 社区处于早期阶段
        
- **Bot 定位**：
    
    - 社区气氛组
        
    - 创作灵感助手
        
    - 每日互动主持人
        
    - 翻译助手
        
- **核心目标**：
    
    - 降低新用户参与社区的门槛
        
    - 鼓励用户主动分享创作想法
        
    - 提供持续、低压力的每日互动
        
    - 打通不同语言用户之间的交流
        
- **MVP 暂不做**：
    
    - 积分系统
        
    - 等级系统
        
    - 复杂经济系统
        
    - 用户排行榜
        
    - 自动审核 / 自动封禁
        
    - 复杂 AI 聊天
        

---

2. ## 功能优先级
    

### P0 — 必须实现

1. 🗳️ 每日投票
    
2. 🎨 每日创作题
    
3. 🎲 `/idea` 随机灵感
    
4. 🌐 消息翻译为英语
    

### P1 — MVP 后可以加入

1. 用户投稿创作题
    
2. 创作题分类
    
3. 投票结果统计
    
4. 每周创作主题
    
5. 灵感题目收藏 / 去重
    

---

3. ## 🗳️ 每日投票
    

### 目标

通过低门槛、有趣的问题让用户每天至少进行一次互动。

### 基本机制

- Bot 每天固定时间发布一条投票消息
    
- 每次投票包含：
    
    - 标题
        
    - 问题
        
    - 3～5 个选项
        
    - 可选的简短说明
        
- 用户直接通过 Discord Poll 或按钮参与
    
- 每个用户只能投票一次
    
- 投票结束后 Bot 自动公布结果
    

### 投票类型

#### A. 创作相关

例如：

> 如果你的 OC 穿越到现代，最可能从事什么工作？

- 🎨 艺术家
    
- 💻 程序员
    
- 📚 老师
    
- ☕ 咖啡店老板
    
- 💀 当场失业
    

#### B. 同人相关

例如：

> 如果你的 CP 一起旅行，谁负责做攻略？

- A
    
- B
    
- 两个人都不做
    
- 一个负责计划，一个负责把计划搞砸
    

#### C. 社区互动

例如：

> 你最喜欢哪种创作方式？

- 🎨 画画
    
- ✍️ 写作
    
- 📷 摄影
    
- 🎭 Cosplay
    
- 🧵 手作
    

#### D. 纯娱乐

例如：

> 你的 OC 如果变成猫，第一件事会做什么？

### 投票内容要求

- 避免过于严肃
    
- 避免政治 / 宗教 / 敏感话题
    
- 优先选择能够让创作者联想到自己的角色、作品或经历的问题
    
- 问题应该能够在 5～10 秒内理解
    
- 选项应该具有一定趣味性
    
- 不要求用户拥有特定作品才能参与
    

### 投票配置

建议放在配置文件中：

```YAML
daily_poll:
  enabled: true
  channel_id: "CHANNEL_ID"
  post_time: "18:00"
  timezone: "Asia/Singapore"
  duration_hours: 24
  options_per_poll:
    min: 3
    max: 5
```

---

4. ## 🎨 每日创作题
    

### 目标

这是 Bot 的核心功能之一。

重点不是“让用户回答问题”，而是：

> **给用户一个可以立即拿来画、写、设计 OC 或创作同人作品的 Prompt。**

### 基本机制

- 每天发布 1 个创作 Prompt
    
- 可以和每日投票同时发布，也可以错开
    
- 用户可以直接回复 Prompt
    
- Bot 不要求用户必须创作
    
- 重点是降低“我今天不知道创作什么”的门槛
    

### Prompt 类型

建议支持分类：

```Plain
OC
Fanart
Fanfiction
Character
Relationship
Worldbuilding
Writing
Drawing
AU
What-if
Funny
Challenge
```

### 示例

#### OC

> 🎨 今日创作题 给你的 OC 设计一套完全不符合 TA 平时风格的衣服。

#### Relationship

> 💕 如果你的 CP 被迫一起经营一家咖啡店，谁会先崩溃？

#### Writing

> ✍️ 写一个角色凌晨三点收到一条来自十年后的短信。

#### Worldbuilding

> 🌎 你的世界里有没有一种只有孩子才知道的秘密？

#### What-if

> 💭 如果你的 OC 一觉醒来发现所有人都忘记了 TA，TA 会怎么做？

## Prompt 要求

每个 Prompt 应：

- 简短
    
- 有明确创作方向
    
- 留有自由发挥空间
    
- 不限制用户必须画 / 写什么
    
- 可以在 5 分钟内开始创作
    
- 尽量能够同时适用于不同创作形式
    

---

5. ## 🎲 `/idea` 随机灵感
    

### 目标

让用户在**任何时候**都可以向 Bot 要一个创作灵感。

### Command

```Plain
/idea
```

### Bot 返回：

```Plain
🎲 Your random idea:

Draw your OC wearing an outfit
they would NEVER normally wear.

Bonus:
🌧️ It's raining.
🥤 They're holding a drink.
👀 And they've just met someone they didn't want to see.
```

### 可选参数

建议支持：

```Plain
/idea
/idea category:oc
/idea category:fanart
/idea category:writing
/idea category:relationship
/idea category:worldbuilding
```

### Category

```Plain
random
oc
fanart
fanfiction
writing
relationship
worldbuilding
au
funny
challenge
```

默认：

```Plain
category = random
```

### 随机机制

不要简单地随机一句话。

可以采用：

```Plain
Base Prompt
+
Optional Constraint
+
Optional Bonus
```

例如：

```Plain
Base:
Your OC meets their future self.

Constraint:
It happens in a convenience store.

Bonus:
Neither of them recognizes the other.
```

最终生成：

> Your OC meets their future self in a convenience store.
> 
> Neither of them recognizes the other.

这样可以组合出大量不同 Prompt。

---

6. ## 🌐 消息翻译
    

### 目标

默认将用户消息翻译成**英语**，帮助不同语言用户交流。

### MVP 交互方式

**不要默认翻译频道里的所有消息。**

推荐：

```Plain
右键消息
→ Apps
→ Translate to English
```

或者：

```Plain
/translate
```

然后选择 / 回复目标消息。

### 默认语言

```YAML
translation:
  default_target_language: "en"
```

### 行为

用户选择：

> Translate to English

Bot 回复：

```Plain
🌐 Translation

Original:
今日は絵を描く気分じゃない……

English:
I don't feel like drawing today...
```

### 翻译原则

- 保留原意
    
- 保留语气
    
- 不要过度正式化
    
- 保留 emoji
    
- 保留 fandom / OC / CP 等社区术语
    
- 不要擅自解释用户内容
    
- 不需要附加 AI 评论
    

### 特殊术语

未来可以维护一个社区词典：

```YAML
glossary:
  OC: Original Character
  CP: Ship / Pairing
  同人: fanworks
  梦女: self-insert / character-focused fandom terminology
```

但 **MVP 可以暂时不实现 Glossary**。

---

7. ## 💡 用户投稿创作题
    

虽然不是第一版必须功能，但建议从架构上预留。

用户可以：

```Plain
/submit-idea
```

提交：

```Plain
category: OC
prompt: Draw your OC as a villain.
```

Bot：

1. 保存 Prompt
    
2. 标记为 `pending`
    
3. 管理员审核
    
4. 审核通过
    
5. 加入 Prompt Pool
    
6. 未来随机出现在 `/idea` 或每日创作题中
    

数据状态：

```Plain
pending
approved
rejected
archived
```

---

8. ## 🤖 Bot 人格
    

Bot 不应该表现得像一个客服。

定位：

> **一个住在服务器里的、稍微有点怪的创作编辑 / 气氛组。**

风格：

- 轻松
    
- 温和
    
- 有一点幽默
    
- 不过度说教
    
- 不强迫互动
    
- 鼓励创作
    
- 不评价用户作品好坏
    
- 不抢用户话题
    

#### 推荐语气

```Plain
🎨 Today's prompt is here.

No pressure to participate.
But if you make something from it,
we'd love to see it.
```

或者：

```Plain
🎲 You asked for an idea.

Here is your problem now:

Your OC has to attend a formal event
wearing something completely ridiculous.
```

#### 避免

```Plain
大家快来参加活动！
不要潜水！
快点发作品！
```

Bot 应该是**邀请用户参与，而不是催促用户参与**。

---

9. ## 📅 推荐 MVP 每日流程
    

建议每天制造 **2 个固定事件**：

```Plain
18:00
🗳️ Daily Poll

↓

20:00
🎨 Daily Creative Prompt
```

用户任何时候都可以：

```Plain
/idea
```

需要翻译时：

```Plain
Right click message
→ Apps
→ Translate to English
```

因此 Bot 的存在感是：

```Plain
每日固定出现
+
用户主动召唤
+
偶尔参与聊天
```

而不是持续刷屏。

---

10. ## 🗂️ 推荐数据结构
    

Agent 可以先按下面的模型设计：

```Plain
Bot
├── commands/
│   ├── idea
│   ├── translate
│   └── submit_idea
│
├── scheduled/
│   ├── daily_poll
│   └── daily_prompt
│
├── services/
│   ├── idea_service
│   ├── poll_service
│   ├── translation_service
│   └── moderation_service
│
├── data/
│   ├── prompts
│   ├── polls
│   └── glossary
│
└── config/
    └── config.yaml
```

---

11. ## 🎯 MVP 成功标准
    

不要以“Bot 有多少功能”作为成功标准。

更重要的是观察：

```Plain
Daily Poll participation
Daily Prompt participation
/idea 使用次数
Translation 使用次数
用户主动投稿 Prompt 数量
```

尤其关注：

> **有多少用户因为 Bot 的 Prompt 而开始了一次创作 / 分享了一次创作想法。**

最终希望形成：

```Plain
Bot 提供灵感
      ↓
用户产生想法
      ↓
用户分享
      ↓
其他用户回应
      ↓
产生新的想法
      ↓
用户投稿新的 Prompt
      ↓
Prompt Pool 越来越丰富
      ↓
Bot 提供更好的灵感
```