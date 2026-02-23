# Sprint Planner — ADX

## Default Credentials
- **SM Login:** username: `scrummaster` / password: `Sprint@2024`
- **Team Members:** Just open the link and pick your name

## Local Run
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Deploy to Render (Free)

1. Push to GitHub:
```bash
git init
git add .
git commit -m "Initial sprint planner"
git remote add origin https://github.com/YOUR_USERNAME/sprint-planner.git
git push -u origin main
```

2. Go to [render.com](https://render.com) → New → Blueprint
3. Connect your GitHub repo
4. Render will auto-detect `render.yaml` and set up everything
5. First deploy: SM login = `scrummaster` / `Sprint@2024`

## Change SM Password After Deploy
Visit `/admin/` → Login → Users → Change password for scrummaster

## Workflow
1. SM logs in at `/login/`
2. SM adds team members via SM Panel
3. Team members open the URL → pick their name → Join
4. SM creates user stories from the Board
5. SM triggers voting per story from SM Panel or Vote Room
6. Team votes with Fibonacci cards (live updates every 3 sec)
7. SM closes voting → sees average
8. SM assigns final SP to story (to owner) and stream SPs to members from Board → 🎯 Assign SP
