import pandas as pd
import xgboost as xgb
import pickle as pkl
from sklearn.metrics import mean_absolute_error
import os
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import RandomizedSearchCV, train_test_split
pd.set_option('display.max_columns', None)

''' PIPELINE
User -> Intent (delay query)
     -> Collect info (station, delay, destination)
     -> XGBoost model
     -> Response
     
Running this file once to create all pickle files required for later use
'''

def encode(s_codes):

    if not os.path.exists('Station_code_enc.pkl'):
        le = LabelEncoder()
        encoded_data = le.fit_transform(s_codes)

        with open('Station_code_enc.pkl', 'wb') as f:
            pkl.dump(le, f)
    else:
        with open('Station_code_enc.pkl', 'rb') as f:
            le = pkl.load(f)
            encoded_data = le.transform(s_codes)

    return encoded_data


def build_feature_set(data: pd.DataFrame) -> pd.DataFrame:
    #Features achieve MAE of around 1.9-2.1 compared to 1.4-1.6 mean delay, so its good enough

    feature_set = data.copy()

    feature_set['Station_code'] = data['location']
    feature_set['Reason'] = data['late_canc_reason'].fillna(0)

    feature_set['journey_id'] = (
            feature_set['rid'].astype(str) + "_" +
            feature_set['date_of_service'].astype(str)
    )

    feature_set['Station_code_enc'] = encode(feature_set['Station_code'])


    time_cols = [
        'planned_arrival_time', 'actual_arrival_time',
        'planned_departure_time', 'actual_departure_time'
    ]

    for col in time_cols:
        feature_set[col] = pd.to_datetime(feature_set[col], format='%H:%M', errors='coerce')

    feature_set['arrival_delay'] = (
        feature_set['actual_arrival_time'] - feature_set['planned_arrival_time']
    ).dt.total_seconds() / 60

    feature_set['departure_delay'] = (
        feature_set['actual_departure_time'] - feature_set['planned_departure_time']
    ).dt.total_seconds() / 60

    feature_set[['arrival_delay', 'departure_delay']] = feature_set[
        ['arrival_delay', 'departure_delay']
    ].fillna(0)

    feature_set['current_delay'] = feature_set['departure_delay']


    feature_set['hour'] = feature_set['planned_arrival_time'].dt.hour
    feature_set['hour'] = feature_set['hour'].fillna(
        feature_set['planned_departure_time'].dt.hour
    )

    feature_set['day_of_week'] = pd.to_datetime(
        feature_set['date_of_service'], errors='coerce'
    ).dt.dayofweek.fillna(0)

    #Detect station bias
    feature_set['mean_station_delay'] = feature_set.groupby('Station_code')['departure_delay'].transform('mean')
    feature_set['std_station_delay'] = feature_set.groupby('Station_code')['departure_delay'].transform('std')

    #save these features for prediction later
    saved_features = feature_set[['Station_code', 'mean_station_delay', 'std_station_delay']].drop_duplicates()
    saved_features.to_csv('Station_mean_std.csv')

    #Remove unusable columns
    drop_cols = [
        'location',
        'late_canc_reason',
        'rid',
        'date_of_service',
        'planned_arrival_time',
        'actual_arrival_time',
        'planned_departure_time',
        'actual_departure_time',
        'journey_id',
        'Station_code'
    ]
    feature_set = feature_set.drop(columns=[c for c in drop_cols if c in feature_set.columns])

    return feature_set

def tune_hyperparameters(model, X, y):
    #Best hyperparameters: {'subsample': 0.7, 'n_estimators': 100, 'max_depth': 3, 'learning_rate': 0.1}

    param_grid = {
        'n_estimators': [50, 100, 500],
        'max_depth': [3, 5, 7],
        'learning_rate': [0.01, 0.1, 1],
        'subsample': [0.7, 0.8, 0.9]
    }

    search = RandomizedSearchCV(model, param_distributions=param_grid, n_iter=10, cv=5, verbose=2, random_state=42)

    search.fit(X, y)

    print(f'Best Params: {search.best_params_}')

def extract_routes(stops: list) -> dict:
    '''
    Find all possible combinations of WEY -> WAT
    '''
    routes = {}
    num_routes = 0
    start = 'WEY'
    end = 'WAT'
    route = []

    for stop in stops:
        if stop == start:
            route = []
            route.append(stop)

        elif stop == end:
            route.append(stop)
            if route not in routes.values():
                routes[num_routes] = route
                num_routes += 1

        else:
            route.append(stop)

    return routes


def predict_delay(model, current_station, destination, current_delay, reason, hour, day):
    mean_std = pd.read_csv('Station_mean_std.csv')



if __name__ == '__main__':

    model = xgb.XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.1, subsample=0.7)
    data = pd.read_csv('2025_service_details.csv')

    #Clean outliers
    station_counts = data['location'].value_counts()
    valid_stations = station_counts[station_counts >= 100].index
    data = data[data['location'].isin(valid_stations)]

    routes = extract_routes(data['location'])
    print(f'Possible Routes: {routes}')


    features = build_feature_set(data)
    print(features)
'''
    X, y = features.drop(columns=['arrival_delay', 'departure_delay']), features['arrival_delay']
    #tune_hyperparameters(model, X, y)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3)
    
    model.fit(X_train, y_train)

    print(f'Mean Delay {y_train.mean()}')
    preds = model.predict(X_test)

    print("MAE:", mean_absolute_error(y_test, preds))'''

