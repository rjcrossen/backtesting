import lseg.data as ld
from lseg.data.session import Session
import pandas as pd
from abc import ABC
from abc import abstractmethod
import matplotlib.pyplot as plt

class Strategy(ABC):
    def __init__(self, start, end, universe, cash, session: Session):
        self.start = start
        self.end = end
        self.current_date = start
        self.cash = cash
        self.universe = universe
        self.universe_history = self.get_data()
        self.historical_dates = self.universe_history.index.tolist()
        self.portfolio = dict()
        self.portfolio_history = pd.DataFrame(index=self.historical_dates, columns=['total_value', 'portfolio_value', 'rebalanced']) # type: ignore[attr-defined]
        self.is_rebalanced = False
        self.execution_cost = 0
        self.financing_cost = 0
    
    def set_execution_cost(self, cost_in_bps):
        """
        Set the execution cost for each trade.

        Args:
            cost_in_bps: Execution cost in basis points.
        """

        self.execution_cost = cost_in_bps / 10000

    def set_financing_cost(self, cost):
        """
        Set the daily financing cost for holding short positions.
        """

        self.financing_cost = cost

    def apply_financing_fee(self):
        for ticker in self.portfolio.keys():
            if self.portfolio[ticker] < 0:
                self.cash -= self.portfolio[ticker] * self.financing_cost


    def get_data(self):
        """
        Take universe and get the data for the relevant timeframe as a pandas dataframe

        Very crude solution for now that just drops NAs because I want to actually get things done
        """
        universe_history =  ld.get_history(self.universe, fields=['TRDPRC_1'], start=self.start, end=self.end)
        universe_history.dropna(inplace=True)
        return universe_history

    def buy(self, ticker, quantity):
        current_price = self.universe_history.loc[self.current_date, ticker] 
        if current_price * quantity > self.cash:
            print("Insufficient cash for trade.")
            return
        trade_cost = current_price * quantity
        execution_fee = trade_cost * self.execution_cost
        self.cash -= (trade_cost + execution_fee)
        if ticker not in self.portfolio:
            self.portfolio[ticker] = quantity
        else:
            self.portfolio[ticker] += quantity
        self.is_rebalanced = True
        
        
    def sell(self, ticker, quantity="all"):
        """
        This function allows you to sell more of a security than you own (i.e., take a short position)
        """

        current_price = self.universe_history.loc[self.current_date, ticker]
        trade_size = current_price * self.portfolio[ticker]
        execution_fee = trade_size * self.execution_cost
        if quantity == "all":
            self.cash += trade_size - execution_fee 
            self.portfolio.pop(ticker)
        else:
            self.cash += trade_size - execution_fee
            self.portfolio[ticker] -= quantity
        self.is_rebalanced = True

    def liquidate(self, ticker):
        """
        Function that can liquidate a portfolio position easily
        """
        
        if ticker not in self.portfolio or self.portfolio[ticker] == 0:
            print("Cannot liquidate a position that doesn't exist")
            return
        current_price = self.universe_history.loc[self.current_date, ticker]
        trade_size = current_price * self.portfolio[ticker]
        execution_fee = trade_size * self.execution_cost
        self.cash += trade_size - execution_fee
        self.is_rebalanced = True

    @abstractmethod
    def on_data(self, data):
        """
        Method that runs each time new data is presented. Strategy logic goes here.
        """
        pass

    def run(self):
        # Main loop
        for date in self.historical_dates:
            self.is_rebalanced = False
            self.current_date = date
            data = self.universe_history.loc[date]
            self.on_data(data)
            self.apply_financing_fee()

            # Portolio value is defined as value of all holdings + liquid cash
            portfolio_value = sum([self.portfolio[ticker] * data[ticker] for ticker in self.portfolio.keys()])
            self.portfolio_history.loc[date, 'total_value'] = portfolio_value + self.cash
            self.portfolio_history.loc[date, 'portfolio_value'] = portfolio_value
            self.portfolio_history.loc[date, 'rebalanced'] = self.is_rebalanced

    def display_backtest(self):
        # Check if backtest has been ran
        if self.portfolio_history.isna().any().any(): # type: ignore
            print("Backtest has not been run so there is no data to plot")
        plt.plot(self.portfolio_history.index, self.portfolio_history['total_value'], linestyle = '-', color = 'b', label = 'Total Value')
        plt.plot(self.portfolio_history.index, self.portfolio_history['portfolio_value'], linestyle = '-', color='g',  label = 'Portfolio Value')
        plt.legend()
        plt.show()
