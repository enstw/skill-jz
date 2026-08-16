# 長時間處理應防止電腦睡眠

預期跑數分鐘以上的處理或等待(watch CI、build、benchmark、下載)時,防止電腦睡眠。手段依平台自行選擇(macOS、Ubuntu 皆適用),唯一約束:睡眠抑制要隨工作結束自動解除,不留無時限的常駐抑制。

# 持久記憶寫進 repo,不寫機器本地 memory

使用者在多台機器工作,machine-local 的 auto-memory 不會同步。不要寫入新的 memory,也不要依賴既有的 memory index;值得留存的事實記到該 repo 自己的文件(AGENTS.md、DESIGN.md、README 等)。既有的 memory 內容可用 /clear-memory 遷移進 repo。
