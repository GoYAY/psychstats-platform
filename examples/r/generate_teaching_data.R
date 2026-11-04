# Reproducible synthetic teaching datasets; base R only.
options(stringsAsFactors = FALSE)
if (.Platform$OS.type == "windows") {
  suppressWarnings(Sys.setlocale("LC_ALL", "Chinese"))
}

root <- normalizePath(getwd(), mustWork = TRUE)
out_dir <- file.path(root, "examples", "data")
dict_dir <- file.path(out_dir, "dictionaries")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(dict_dir, recursive = TRUE, showWarnings = FALSE)

clamp <- function(x, low, high) pmin(high, pmax(low, x))
write_data <- function(x, name) write.csv(x, file.path(out_dir, paste0(name, ".csv")), row.names = FALSE, fileEncoding = "UTF-8")
write_dict <- function(name, rows) write.csv(rows, file.path(dict_dir, paste0(name, ".csv")), row.names = FALSE, fileEncoding = "UTF-8")

set.seed(20260901)
n <- 360
support <- clamp(round(rnorm(n, 50, 10), 1), 15, 85)
stress <- clamp(round(62 - 0.28 * support + rnorm(n, 0, 8), 1), 10, 90)
wellbeing <- clamp(round(45 - 0.30 * stress + 0.35 * support + rnorm(n, 0, 7), 1), 5, 90)
cross_sectional_survey <- data.frame(id=1:n, age=sample(18:60,n,TRUE), gender=sample(c("female","male","nonbinary"),n,TRUE,c(.53,.44,.03)), social_support=support, stress=stress, well_being=wellbeing)
write_data(cross_sectional_survey, "cross_sectional_survey")

set.seed(20260902)
n <- 180
condition <- rep(c("control","retrieval"), each=n/2)
pre <- clamp(round(rnorm(n, 68, 10),1),30,95)
post <- clamp(round(25 + .68*pre + ifelse(condition=="retrieval",7,0) + rnorm(n,0,7),1),25,100)
learning_experiment <- data.frame(id=1:n, condition=condition, pre_score=pre, post_score=post, gain=round(post-pre,1))
write_data(learning_experiment, "learning_experiment")

set.seed(20260903)
n <- 420
latent <- matrix(rnorm(n*3), ncol=3)
items <- sapply(1:12, function(j) clamp(round(3 + .75*latent[,ceiling(j/4)] + rnorm(n,0,.8)),1,5))
scale_items <- data.frame(id=1:n, items); names(scale_items)[-1] <- paste0("item_",1:12)
write_data(scale_items, "scale_items")

set.seed(20260904)
classes <- 30; per_class <- 24; n <- classes*per_class
class_id <- rep(sprintf("C%02d",1:classes), each=per_class)
teacher_by_class <- clamp(round(rnorm(classes,50,8),1),25,75)
class_effect <- rnorm(classes,0,5)
motivation <- clamp(round(rnorm(n,55,10),1),20,90)
achievement <- clamp(round(35 + .35*motivation + .25*rep(teacher_by_class,each=per_class) + rep(class_effect,each=per_class) + rnorm(n,0,7),1),20,100)
nested_classrooms <- data.frame(student_id=1:n,class_id=class_id,teacher_support=rep(teacher_by_class,each=per_class),motivation=motivation,achievement=achievement)
write_data(nested_classrooms, "nested_classrooms")

set.seed(20260905)
people <- 160; waves <- 4
id <- rep(1:people, each=waves); time <- rep(0:3, people); treatment_person <- sample(c("control","intervention"), people, TRUE)
intercept <- rnorm(people,50,7); slope <- rnorm(people,2,1)
outcome <- round(rep(intercept,each=waves)+rep(slope,each=waves)*time+ifelse(rep(treatment_person,each=waves)=="intervention",2.2*time,0)+rnorm(people*waves,0,4),1)
longitudinal_growth <- data.frame(id=id,time=time,treatment=rep(treatment_person,each=waves),outcome=clamp(outcome,15,100))
write_data(longitudinal_growth, "longitudinal_growth")

set.seed(20260906)
n <- 250
messy_survey <- data.frame(id=1:n, age_text=as.character(sample(18:60,n,TRUE)), gender=sample(c("female","Female ","male","M","nonbinary"),n,TRUE), stress=round(rnorm(n,50,10),1), submitted_at=as.character(as.Date("2026-01-01")+sample(0:90,n,TRUE)))
messy_survey$age_text[c(8,77)] <- c("twenty","")
messy_survey$stress[c(12,99)] <- NA
messy_survey$stress[155] <- 99
messy_survey <- rbind(messy_survey, messy_survey[c(20,45),])
write_data(messy_survey, "messy_survey")

dict <- function(names, labels, types, roles, values="") data.frame(name=names,label=labels,type=types,role=roles,values=values)
write_dict("cross_sectional_survey", dict(names(cross_sectional_survey), c("ID","Age","Gender","Social support","Stress","Well-being"), c("integer","integer","categorical","numeric","numeric","numeric"), c("id","predictor","predictor","predictor","predictor","outcome"), c("","18-60","female|male|nonbinary","15-85","10-90","5-90")))
write_dict("learning_experiment", dict(names(learning_experiment), c("ID","Condition","Pretest","Posttest","Gain"), c("integer","categorical","numeric","numeric","numeric"), c("id","group","baseline","outcome","derived"), c("","control|retrieval","30-95","25-100","")))
write_dict("scale_items", dict(names(scale_items), c("ID",paste0("Scale item ",1:12)), c("integer",rep("integer",12)), c("id",rep("item",12)), c("",rep("1-5",12))))
write_dict("nested_classrooms", dict(names(nested_classrooms), c("Student ID","Class ID","Teacher support","Motivation","Achievement"), c("integer","categorical","numeric","numeric","numeric"), c("id","cluster","level2 predictor","level1 predictor","outcome")))
write_dict("longitudinal_growth", dict(names(longitudinal_growth), c("Person ID","Time","Treatment","Outcome"), c("integer","integer","categorical","numeric"), c("id","time","group","outcome"), c("","0-3","control|intervention","15-100")))
write_dict("messy_survey", dict(names(messy_survey), c("ID","Age text","Raw gender","Stress","Submission date"), c("integer","string","string","numeric","string"), c("id","dirty predictor","dirty category","dirty outcome","dirty date")))

json_escape <- function(x) gsub('"', '\\"', gsub('\\\\', '\\\\\\', x))
to_json <- function(x) {
  if (is.null(x)) return("null")
  if (is.list(x)) {
    if (!is.null(names(x)) && all(nzchar(names(x)))) return(paste0("{",paste(sprintf('"%s":%s',json_escape(names(x)),vapply(x,to_json,"")),collapse=","),"}"))
    return(paste0("[",paste(vapply(x,to_json,""),collapse=","),"]"))
  }
  if (is.logical(x)) return(ifelse(x,"true","false"))
  if (is.numeric(x)) return(as.character(x))
  if (length(x)>1) return(paste0("[",paste(sprintf('"%s"',json_escape(x)),collapse=","),"]"))
  sprintf('"%s"',json_escape(x))
}
num <- function(min,max,missing=FALSE) list(type="numeric",min=min,max=max,allow_missing=missing)
int <- function(min,max) list(type="integer",min=min,max=max)
cat_spec <- function(levels) list(type="categorical",levels=as.list(levels))
truth <- list(generator_version="1.0", datasets=list(
  cross_sectional_survey=list(file="cross_sectional_survey.csv",rows=360,seed=20260901,columns=list(id=int(1,360),age=int(18,60),gender=cat_spec(c("female","male","nonbinary")),social_support=num(15,85),stress=num(10,90),well_being=num(5,90))),
  learning_experiment=list(file="learning_experiment.csv",rows=180,seed=20260902,columns=list(id=int(1,180),condition=cat_spec(c("control","retrieval")),pre_score=num(30,95),post_score=num(25,100),gain=num(-70,70))),
  scale_items=list(file="scale_items.csv",rows=420,seed=20260903,columns=c(list(id=int(1,420)),setNames(replicate(12,int(1,5),simplify=FALSE),paste0("item_",1:12)))),
  nested_classrooms=list(file="nested_classrooms.csv",rows=720,seed=20260904,columns=list(student_id=int(1,720),class_id=list(type="string"),teacher_support=num(25,75),motivation=num(20,90),achievement=num(20,100))),
  longitudinal_growth=list(file="longitudinal_growth.csv",rows=640,seed=20260905,columns=list(id=int(1,160),time=int(0,3),treatment=cat_spec(c("control","intervention")),outcome=num(15,100))),
  messy_survey=list(file="messy_survey.csv",rows=252,seed=20260906,intentional_issues=as.list(c("missing_values","duplicate_ids","inconsistent_categories","outliers")),columns=list(id=int(1,250),age_text=list(type="string",allow_missing=TRUE),gender=list(type="string"),stress=num(0,100,TRUE),submitted_at=list(type="string")))
))
writeLines(to_json(truth), file.path(out_dir,"generation_truth.json"), useBytes=TRUE)
message("Generated six teaching datasets in ", out_dir)
