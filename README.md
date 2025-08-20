# Amazon KDP Book Scraper

Un Actor Apify puissant pour extraire des données complètes de livres depuis la plateforme Amazon Kindle Direct Publishing (KDP). Cet Actor peut collecter des informations détaillées sur les livres incluant les titres, auteurs, prix, notes, avis clients et métadonnées.

## 🚀 Fonctionnalités

- **Recherche avancée** : Recherche par mots-clés avec support de multiples termes
- **Filtrage intelligent** : Filtrage par catégories, prix, notes minimales
- **Extraction complète** : Titre, auteur, prix, notes, nombre d'avis, description, date de publication, nombre de pages, langue, ISBN, catégories, image de couverture
- **Avis clients** : Extraction optionnelle des avis clients avec notes, titres, textes, auteurs et dates
- **Gestion des proxies** : Support des proxies Apify pour éviter les blocages
- **Respect des politiques** : Délais configurables entre les requêtes pour respecter les politiques d'Amazon
- **Déduplication** : Suppression automatique des doublons basée sur l'URL

## 📋 Configuration d'entrée

### Paramètres obligatoires

- **searchTerms** (array) : Liste des termes de recherche (ex: ["python programming", "data science"])

### Paramètres optionnels

- **categories** (array) : Catégories à filtrer (ex: ["Computers & Technology", "Business & Money"])
- **maxResults** (number) : Nombre maximum de résultats par recherche (défaut: 100)
- **includeReviews** (boolean) : Inclure les avis clients (défaut: false)
- **minRating** (number) : Note minimale requise (0-5, défaut: 0)
- **priceRange** (object) : Fourchette de prix
  - **min** (number) : Prix minimum
  - **max** (number) : Prix maximum
- **sortBy** (string) : Tri des résultats
  - `relevance` (défaut)
  - `price-low-to-high`
  - `price-high-to-low`
  - `avg-customer-review`
  - `newest-arrivals`
- **proxyConfiguration** (object) : Configuration des proxies
  - **useApifyProxy** (boolean) : Utiliser les proxies Apify
- **requestDelay** (number) : Délai entre les requêtes en secondes (défaut: 2)

## 📊 Données extraites

Chaque livre extrait contient les informations suivantes :

```json
{
  "url": "https://www.amazon.com/dp/XXXXXXXXXX",
  "title": "Titre du livre",
  "author": "Nom de l'auteur",
  "price": 9.99,
  "rating": 4.5,
  "review_count": 1234,
  "description": "Description du livre...",
  "publication_date": "January 1, 2024",
  "page_count": 300,
  "language": "English",
  "isbn": "978-XXXXXXXXXX",
  "categories": ["Programming", "Computer Science"],
  "image_url": "https://images-na.ssl-images-amazon.com/...",
  "reviews": [
    {
      "rating": 5.0,
      "title": "Excellent livre!",
      "text": "Très bien écrit et informatif...",
      "author": "John Doe",
      "date": "Reviewed in the United States on January 15, 2024"
    }
  ]
}
```

## 🔧 Exemple d'utilisation

### Configuration basique

```json
{
  "searchTerms": ["python programming", "machine learning"],
  "maxResults": 50,
  "minRating": 4.0,
  "requestDelay": 3
}
```

### Configuration avancée

```json
{
  "searchTerms": ["data science", "artificial intelligence"],
  "categories": ["Computers & Technology"],
  "maxResults": 100,
  "includeReviews": true,
  "minRating": 4.0,
  "priceRange": {
    "min": 5.0,
    "max": 50.0
  },
  "sortBy": "avg-customer-review",
  "proxyConfiguration": {
    "useApifyProxy": true
  },
  "requestDelay": 2
}
```

## 🛡️ Bonnes pratiques

### Respect des politiques Amazon

- **Délais entre requêtes** : Utilisez un délai d'au moins 2 secondes entre les requêtes
- **Limitation du volume** : Ne dépassez pas 1000 livres par exécution
- **Utilisation de proxies** : Activez les proxies Apify pour les gros volumes
- **Heures creuses** : Exécutez le scraper pendant les heures de faible trafic

### Optimisation des performances

- **Termes de recherche spécifiques** : Utilisez des termes précis pour de meilleurs résultats
- **Filtrage approprié** : Utilisez les filtres pour réduire le nombre de pages à traiter
- **Gestion des erreurs** : L'Actor continue même si certaines pages échouent

## 🚨 Limitations et considérations

- **Respect des ToS** : Assurez-vous de respecter les conditions d'utilisation d'Amazon
- **Détection anti-bot** : Amazon peut détecter et bloquer les requêtes automatisées
- **Structure des pages** : Les sélecteurs peuvent changer si Amazon modifie sa structure
- **Géolocalisation** : Les résultats peuvent varier selon la région

## 🔍 Dépannage

### Problèmes courants

1. **Aucun résultat trouvé**
   - Vérifiez l'orthographe des termes de recherche
   - Essayez des termes plus génériques
   - Vérifiez les filtres appliqués

2. **Erreurs de requête**
   - Augmentez le délai entre les requêtes
   - Activez les proxies Apify
   - Réduisez le nombre de résultats par exécution

3. **Données manquantes**
   - Certains livres peuvent ne pas avoir toutes les informations
   - Les sélecteurs peuvent nécessiter une mise à jour

## 📈 Cas d'usage

- **Recherche de marché** : Analyser la concurrence dans votre niche
- **Veille tarifaire** : Surveiller les prix des livres concurrents
- **Analyse de tendances** : Identifier les sujets populaires
- **Lead generation** : Trouver des auteurs potentiels à contacter
- **Recherche académique** : Collecter des données pour des études de marché

## 🤝 Support

Pour toute question ou problème :

1. Vérifiez cette documentation
2. Consultez les logs d'exécution pour les erreurs
3. Contactez le support Apify si nécessaire

## 📄 Licence

Cet Actor est fourni tel quel. L'utilisateur est responsable du respect des conditions d'utilisation d'Amazon et des lois applicables.

---

**Note importante** : Cet Actor est conçu à des fins éducatives et de recherche. Assurez-vous de respecter les conditions d'utilisation d'Amazon et les lois sur la protection des données applicables dans votre juridiction.
