-- Migration 056: Drop catalog immutability triggers to allow direct in-place editing of catalog offerings and revisions
DROP TRIGGER IF EXISTS benefit_catalog_revision_immutable ON public.benefit_catalog_revisions;
DROP TRIGGER IF EXISTS catalog_offering_immutable ON public.catalog_offerings;
DROP TRIGGER IF EXISTS benefit_relation_immutable ON public.benefit_relations;
DROP TRIGGER IF EXISTS benefit_package_immutable ON public.benefit_packages;

DROP FUNCTION IF EXISTS public.prevent_published_catalog_mutation();
DROP FUNCTION IF EXISTS public.prevent_published_catalog_child_mutation();
