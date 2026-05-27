from core.models import Category, Book

categories = Category.objects.all()
print("=== CATEGORIES ===")
for cat in categories:
    book_count = Book.objects.filter(category=cat, status='AVAILABLE', quantity__gt=0).count()
    print(f"- {cat.name} ({book_count} books)")

print("\n=== BOOKS WITH CATEGORY ===")
books = Book.objects.filter(status='AVAILABLE', quantity__gt=0)
print(f"Total available books: {books.count()}")
for b in books[:10]:
    print(f"- {b.title} | {b.category.name} | Price: {b.price}")
