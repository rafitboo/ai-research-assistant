--
-- PostgreSQL database dump
--

\restrict 5k3KyOzLIgz8d3ODUygvhrlreOicVadDUTev2p1DY7Z62rH0PMQ10ngZ8khvgK2

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, name, email, password_hash, role, subscription_tier) FROM stdin;
1	System Admin	admin@platform.com	1506eecfa92f3cd322582e860b3b5cf5:da131b70ebc15d9cf73877df9e9d991f6765f1f70df94a3f715ad23afdc04921	Admin	Premium
2	rafit	rafit991@gmail.com	0d82bc6e855eb3fdf876b85881d51c8a:8d9ec4a78a1d843b0d7b0f956457ac79d5319f8e880bc77645d0867af5f4dd16	Researcher	Free
\.


--
-- Data for Name: papers; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.papers (id, owner_id, title, authors, publication_year, abstract, extracted_text, reading_status, read_percentage, time_spent_seconds) FROM stdin;
\.


--
-- Data for Name: projects; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.projects (id, title, description, owner_id, created_at) FROM stdin;
\.


--
-- Data for Name: project_members; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.project_members (id, project_id, user_id, role) FROM stdin;
\.


--
-- Name: papers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.papers_id_seq', 1, false);


--
-- Name: project_members_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.project_members_id_seq', 1, false);


--
-- Name: projects_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.projects_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 2, true);


--
-- PostgreSQL database dump complete
--

\unrestrict 5k3KyOzLIgz8d3ODUygvhrlreOicVadDUTev2p1DY7Z62rH0PMQ10ngZ8khvgK2

