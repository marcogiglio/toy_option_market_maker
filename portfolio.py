

class Portfolio:
    def __init__(self, positions):
        self.positions_dict = dict()
        for position in positions:
            name = position['instrument_name']
            self.positions_dict[name] = position

        self.positions = positions

    def delta(self):
        return sum([position['delta'] for position in self.positions])

    def options(self):
        return list(filter(lambda x: x['kind'] == 'option', self.positions))

    def futures(self):
        return list(filter(lambda x: x['kind'] == 'future', self.positions))

    def __str__(self):
        return_str = ''
        for (key, value) in self.__dict__.items():
            return_str += '\n{} : {}'.format(key, value)
        return return_str