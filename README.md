# An Option Market Maker Toy Model for Deribit API

In this repository, the ongoing effort of building a toy option market maker for Deribit. The MM updates the bid and ask spread based on a Karman filter to handle the inventory,
and it has a naive delta hedging strategy by longing or shorting the corrisponding option future.

Inspired by "Option Trading" by Euan Sinclair
