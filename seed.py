from app import app, db, MenuItem, Admin, generate_password_hash

with app.app_context():
    if not MenuItem.query.first():
        menu = [
            ("Masala Dosa","South Indian",90),
            ("Idli Sambar","South Indian",50),
            ("Medu Vada","South Indian",60),
            ("Upma","South Indian",40),

            ("Vada Pav","Maharashtrian",30),
            ("Misal Pav","Maharashtrian",80),
            ("Puran Poli","Maharashtrian",60),
            ("Sabudana Khichdi","Maharashtrian",70),

            ("Dhokla","Gujarati",50),
            ("Thepla","Gujarati",40),
            ("Undhiyu","Gujarati",120),

            ("Chole Bhature","Punjabi",90),
            ("Dal Makhani","Punjabi",120),
            ("Paneer Tikka","Punjabi",140),

            ("Chicken Curry","Non-Veg",150),
            ("Butter Chicken","Non-Veg",180),
            ("Mutton Biryani","Non-Veg",200),

            ("Gulab Jamun","Dessert",40),
            ("Rasgulla","Dessert",40),
            ("Chocolate Brownie","Dessert",80)
        ]

        for m in menu:
            db.session.add(MenuItem(name=m[0], category=m[1], price=m[2]))

    if not Admin.query.first():
        db.session.add(Admin(username="admin", password=generate_password_hash("admin")))

    db.session.commit()
    print("✅ Database seeded with menu and admin user")