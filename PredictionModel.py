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

Run this file once to create all pickle files and datasets required for later use

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
    # Features achieve MAE of around 1.9-2.1 compared to 1.4-1.6 mean delay

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

    feature_set['arrival_delay'] = ((feature_set['actual_arrival_time'] - feature_set['planned_arrival_time'])
                                    .dt.total_seconds() / 60)

    feature_set['departure_delay'] = ((feature_set['actual_departure_time'] - feature_set['planned_departure_time'])
                                      .dt.total_seconds() / 60)

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

    #detect station bias
    feature_set['mean_station_delay'] = feature_set.groupby('Station_code')['departure_delay'].transform('mean')
    feature_set['std_station_delay'] = feature_set.groupby('Station_code')['departure_delay'].transform('std')

    #Save these features for prediction later
    saved_features = feature_set[['Station_code_enc', 'mean_station_delay', 'std_station_delay']].drop_duplicates()
    saved_features.to_csv('Station_mean_std.csv', index=False)

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
    #Best Params: {'subsample': 0.8, 'n_estimators': 50, 'max_depth': 3, 'learning_rate': 0.1}

    param_grid = {
        'n_estimators': [50, 100, 500],
        'max_depth': [3, 5, 7],
        'learning_rate': [0.01, 0.1, 1],
        'subsample': [0.7, 0.8, 0.9]
    }

    search = RandomizedSearchCV(model, param_distributions=param_grid, n_iter=10, cv=5, verbose=2, random_state=42)
    search.fit(X, y)
    print(f'Best Params: {search.best_params_}')


def extract_routes(stops: pd.Series) -> dict:
    '''
    Find all possible combinations of WEY -> WAT.
    '''

    encoded_stops = encode(stops)

    start = encode(['WEY'])[0]
    end = encode(['WAT'])[0]

    routes = {}
    num_routes = 0
    route = []

    for stop in encoded_stops:
        if stop == start:
            route = [stop]
        elif stop == end:
            route.append(stop)
            if route not in routes.values():
                routes[num_routes] = route
                num_routes += 1
            route = []  # reset so we capture the next WEY->WAT run too
        else:
            route.append(stop)

    return routes


def select_routes(current, destination, routes):
    valid_routes = [
        stations
        for stations in routes.values()
        if (
                current in stations and
                destination in stations and
                stations.index(current) < stations.index(destination)
        )
    ]

    if not valid_routes:
        raise ValueError("No valid routes found")

    return valid_routes


def predict_delay(
        current_station,
        destination,
        current_delay,
        reason,
        hour,
        day,
        routes
):

    with open('Prediction_Model.pkl', 'rb') as f:
        model = pkl.load(f)

    mean_std = pd.read_csv("Station_mean_std.csv")
    enc_current, enc_destination = encode([current_station])[0],encode([destination])[0]

    valid_routes = select_routes(enc_current, enc_destination, routes)
    route = valid_routes[0]

    start_idx = route.index(enc_current)
    end_idx = route.index(enc_destination)
    remaining_route = route[start_idx + 1:end_idx + 1]

    predicted_delay = current_delay  # sensible default if route is empty

    for station_enc in remaining_route:
        stats = mean_std[mean_std['Station_code_enc'] == station_enc]

        if stats.empty:
            mean_delay = 0.0
            std_delay = 0.0
        else:
            mean_delay = stats['mean_station_delay'].values[0]
            std_delay = stats['std_station_delay'].values[0]

        X = pd.DataFrame([{
            'Reason': reason,
            'Station_code_enc': station_enc,
            'current_delay': current_delay,
            'hour': hour,
            'day_of_week': day,
            'mean_station_delay': mean_delay,
            'std_station_delay': std_delay
        }])

        predicted_delay = model.predict(X)[0]

    return round(float(predicted_delay), 2)


if __name__ == '__main__':

    #Uncomment to test - Example usage
    '''data = pd.read_csv('dataset.csv')

    routes = extract_routes(data['location'])
    prediction = predict_delay(
        current_station="SOU",
        destination="CLJ",
        current_delay=10,
        reason=832,
        hour=16,
        day=4,
        routes=routes
    )

    print(f"Predicted delay at destination: {prediction} minutes")'''


    years = [2022,2023,2024,2025]
    dfs = []

    for y in years:
        temp = pd.read_csv(f'./data/{y}_service_details.csv')
        dfs.append(temp)

    data = pd.concat(dfs, ignore_index=True)
    station_counts = data['location'].value_counts()
    frequent_stations = station_counts[station_counts >= 100].index
    data = data[data['location'].isin(frequent_stations)] #Remove all low frequency stations
    data.to_csv('dataset.csv')
    print('Large Dataset Built')


    features = build_feature_set(data)
    X, y = features.drop(columns=['arrival_delay', 'departure_delay']), features['departure_delay']
    #tune_hyperparameters(model, X, y) #Already evaluated using test-train split
    print('Feature Set Built')

    model = xgb.XGBRegressor(n_estimators=50, max_depth=3, learning_rate=0.1, subsample=0.8)
    model.fit(X, y)

    with open('Prediction_Model.pkl', 'wb') as f:
        pkl.dump(model, f)

    print('Model saved')
