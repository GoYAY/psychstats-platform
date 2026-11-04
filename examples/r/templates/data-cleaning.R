# Replace the file name and column names with your own dataset.
d <- read.csv("your_data.csv", stringsAsFactors=FALSE)
stopifnot(all(c("id", "age_text", "gender", "stress") %in% names(d)))
sum(duplicated(d$id)); colSums(is.na(d))
d <- d[!duplicated(d$id), ]
d$age <- suppressWarnings(as.numeric(d$age_text))
d$gender <- trimws(tolower(d$gender))
summary(d$stress); table(d$gender, useNA="ifany")
# Record exclusions and recoding rules before modeling.
