d <- read.csv("your_data.csv")
t.test(d$score,conf.level=.95)$conf.int
# The interval procedure's assumptions and sampling design matter.
