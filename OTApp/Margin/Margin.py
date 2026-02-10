from OTApp.Logger.Logger import AppLogger
from OTApp.Wallet.Wallet import Wallet


class Margin:
    def margin_sufficient(self, leverage, spot_price, totalPremium, lots):
        total_margin_required = totalPremium + (
                lots * float(spot_price)) / leverage
        available_balance = Wallet().getBalances()
        sufficient = False
        if total_margin_required < available_balance:
            AppLogger.logger.info(
                f"Available margin : {available_balance} is sufficient for initiate trade as required "
                f"margin : {total_margin_required} for {lots} lots in BTC")
            sufficient = True
        else:
            AppLogger.logger.warning(
                f"Insufficient margin for BTC {lots} lots ! as "
                f"required is : {total_margin_required} but available is {available_balance}")

        return sufficient
