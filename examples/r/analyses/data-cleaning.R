source("examples/r/analyses/_common.R")
d <- read_data("messy_survey")
raw_n <- nrow(d)
d <- d[!duplicated(d$id), ]
d$gender <- trimws(tolower(d$gender))
d$gender[d$gender == "m"] <- "male"
d$age <- suppressWarnings(as.numeric(d$age_text))
d$stress[d$stress > 90] <- NA_real_
emit(c(raw_rows=raw_n, clean_rows=nrow(d), duplicate_removed=raw_n-nrow(d),
       invalid_age=sum(is.na(d$age)), stress_missing=sum(is.na(d$stress))))
