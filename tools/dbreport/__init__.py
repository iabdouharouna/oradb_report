"""Outillage Python de production du rapport standard des bases Oracle.

Le package expose une CLI permettant de :

* verifier les connexions Oracle du parc (``check``) ;
* collecter un snapshot des bases de production (``collect``) ;
* produire les rapports Markdown / HTML / CSV (``report``) ;
* enchainer l'ensemble (``run``).

Toute la collecte est realisee en **lecture seule** (aucune ecriture DDL/DML).
"""

__all__ = ["__version__"]
__version__ = "1.0.0"
