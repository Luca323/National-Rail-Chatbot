import pandas as pd
import xgboost as xgb
import datetime as dt
from sklearn.model_selection import RandomizedSearchCV
pd.set_option('display.max_columns', None)


def build_feature_set(data) -> pd.DataFrame:
    feature_set = pd.DataFrame()
    feature_set[['Station_code', 'Reason']] = data[['location', 'late_canc_reason']]

    time_cols = ['planned_arrival_time', 'actual_arrival_time',
                 'planned_departure_time', 'actual_departure_time']

    for col in time_cols:
        data[col] = pd.to_datetime(data[col], format='%H:%M', errors='coerce')

    #Calculate delays in minutes
    feature_set['arrival_delay'] = (data['actual_arrival_time'] - data['planned_arrival_time']).dt.total_seconds() / 60
    feature_set['departure_delay'] = (data['actual_departure_time'] - data['planned_departure_time']).dt.total_seconds() / 60

    feature_set.fillna(0, inplace=True)

    #Extract hour and day of week
    data['planned_arrival_time'] = pd.to_datetime(data['planned_arrival_time'], format='%H:%M', errors='coerce')

    feature_set['hour'] = data['planned_arrival_time'].dt.hour
    feature_set['hour'] = data['planned_arrival_time'].dt.hour.fillna(data['planned_departure_time'].dt.hour) #use departure time if arrival not available

    feature_set['day_of_week'] = pd.to_datetime(data['date_of_service'], dayfirst=True).dt.dayofweek

    return feature_set

def tune_hyperparameters(model, X, y):
    #Best hyperparameters: {'subsample': 0.7, 'n_estimators': 100, 'max_depth': 5, 'learning_rate': 0.01}

    param_grid = {
        'n_estimators': [50, 100, 500],
        'max_depth': [3, 5, 7],
        'learning_rate': [0.01, 0.1, 1],
        'subsample': [0.7, 0.8, 0.9]
    }

    search = RandomizedSearchCV(model, param_distributions=param_grid, n_iter=10, cv=5, verbose=2, random_state=42)

    search.fit(X, y)

    print(f'Best Params: {search.best_params_}')

if __name__ == '__main__':
    model = xgb.XGBRegressor()
    data = pd.read_csv('2025_service_details.csv')
    features = build_feature_set(data)

    X, y = features.drop(columns=['arrival_delay', 'departure_delay', 'Station_code']), features['departure_delay']

    tune_hyperparameters(model, X, y)


