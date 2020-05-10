metier & df_site
=================

Composants (documentation)
https://github.com/twbs/bootstrap
https://github.com/SortableJS/Sortable
https://github.com/select2/select2
https://github.com/flatpickr/flatpickr
https://github.com/MohammadYounes/AlertifyJS
https://github.com/ckeditor/ckeditor5
https://pypi.org/project/django-fontawesome-5/

Django-Floor
    * websockets et signaux
        Candidats : 
            * django-channels 2 + daphnee
                # il y a 10 mois : This is great. I've been having performance and crashing issues with Daphne. I'll wait to test this PR before opening an issue, hopefully it goes away :)
                # Yeah, I remember that @gordon had stability issues, and I wouldn't be suprised if the switch fixed that either!
                # We didn’t want to use Daphne anymore. It was a nightmare.  https://medium.com/@ebsaral/our-experience-with-django-channels-on-heroku-f821213a57a1
                dépendances de daphne : pycparser, cffi, cryptography, txaio, autobahn, hyperlink, PyHamcrest, Automat, constantly, zope.interface, incremental, pyopenssl, pyasn1, pyasn1-modules, service-identity, twisted, daphne
                * daphne conseille d'avoir un process pour les WS et un process pour le HTTP comme gunicorn (sous-entendu gunicorn est plus performant)
            * uvicorn
                dépendances d'uvicorn : click-7.1.1 h11-0.9.0 httptools-0.1.1 uvicorn-0.11.3 uvloop-0.14.0 websockets-8.1
    * configuration 
        * A découpage en plusieurs fichiers
        * B fichiers .ini ou .env
        * C fichiers .py
        * D variables d'environnement
        * E configuration par défaut complète
        * F référence entre settings
        * G relance des process en cas de changement de config
        * H page web de configuration
        Candidats : 
            * django-floor -> OK : A, B, C, D, E, F 
            * django-environ -> OK : D 
            * python-decouple -> OK : A, B, D
            * django-constance -> OK : H
            * django-configurations -> OK : A, C
            * django-split-settings -> OK : A, C
            * django-dotenv -> trop vieux
            * django-flexisettings -> OK : A, C
            * django-livesettings -> OK : H
            * django-extra-settings -> OK : H
    * pages complètes
    * utilitaires divers  
    * configuration récupérée

Widgets : 
    ok Fenêtres modales
    ok Notifications
    ok datetime -> flatpicker
    ok date -> flatpicker
    ok time -> flatpicker
    ok autocomplete 
    ok plusieurs éditeurs sur la même page
    ok éditeurs dans des fenêtres modales
    ok upload d'images
    ok font-awesome
    ok barres de progression avec signal
    ok ajouter un drapeau au modèle => tester select2 avec le drapeau et un lien
    ok django-smart-selects (sélections liées), y compris dans les modales
    ok select2 et overflow
    ok sortable inlines + formset
    ok confirmation avant submit via POST {% confirm "Êtes-vous sûr ?" %} 
    ok raccourcis {% shortcut "f" %}
    ok menu vertical avec des éléments => breadcrumbs.html
    ok typescript
    ok chargement différé des images
    ok images en plein écran avec parcours des images d'une page
    ok django-pipeline
    tables dynamiques pour remplacer le site d'admin
        -> actions sur la sélection
        -> filtres
        -> barre de recherche
        -> pagination
        -> tri par colonne
        -> liens fonctionnels (via l'anchor)
    projets distincts pour df_websockets, df_site et df_config
    tester un appel Ajax avec le header pour valider le window_key
    preview de PDF


+-------------------------------------------------------------------------------+
| widget           |    base    |     modal     | formset       | extra formset |
|------------------|------------|---------------|---------------|---------------|
| date             |     ok     |      ok       |               |               |
|------------------|------------|---------------|---------------|---------------|
| datetime         |     ok     |      ok       |               |               |
|------------------|------------|---------------|---------------|---------------|
| time             |     ok     |      ok       |               |               |
|------------------|------------|---------------|---------------|---------------|
| smart_selects    |     ok     |      ok       |               |               |
|------------------|------------|---------------|---------------|---------------|
| Ckeditor         |     ok     |      ok       |               |               |
|------------------|------------|---------------|---------------|---------------|
| select2          |     ok     |      ok       |               |               |
+-------------------------------------------------------------------------------+
| confirmation     |     ok     |      ok       |               |               |
+-------------------------------------------------------------------------------+


CKEditor : 
    ok hauteur
    ok upload d'images
    ok smileys
    ok espaces insécables
    ok majuscules auto
    ok autocorrect
    ok lignes horizontales
    ok sauts de page
    ckeditor5-footnote
    blocs de couleurs
    petites capitales
    mention
 
